"""Chunked CSV/Parquet reading with optional reservoir sampling.

dataset.raw_files/train_file/test_file accept, per file: plain CSV,
CSV with a compression suffix pandas infers from the name (.csv.gz,
.csv.bz2, .csv.xz, and .csv.zip provided the zip holds exactly one
member - pandas' own read_csv handles all of these natively, chunked
reading included, nothing in this module is compression-aware), or
.parquet (dispatched to pyarrow, already a hard dependency). Not
supported: .rar or any multi-member archive - extract those yourself
first and point raw_files at the CSV/Parquet file(s) inside. A rar
reader needs an external unrar/7z binary on PATH with no reliable
cross-platform story, and a multi-member zip has no single obvious
file to pick; both are worse trade-offs than "extract it first."

Two independent knobs (dataset.chunk_size / dataset.max_rows):

- chunk_size bounds memory during the read/downcast phase only, by
  reading each file chunk_size rows at a time and downcasting float64
  columns to float32 immediately (same rationale as the IDS project's
  loader: CICFlowMeter-style features are counts/durations/rates that
  don't need float64 precision). On its own this does NOT prevent OOM
  on a dataset bigger than RAM, since every downstream step (audit
  checks, sklearn/imblearn fitting) still needs one consolidated
  in-memory array.

- max_rows is what actually bounds the final in-memory size: a uniform
  reservoir sample (Algorithm R) across the whole stream of rows, so
  the retained dataset never exceeds max_rows regardless of source
  file size. This is a statistical sample, not the exact full dataset.
  It operates at the row level: if dataset.split_mode is "grouped",
  sampling may fragment session groups across the sample boundary;
  that's a documented limitation, not a bug fix candidate for v1.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _downcast_chunk(df: pd.DataFrame) -> pd.DataFrame:
    float_cols = df.select_dtypes(include=["float64"]).columns
    if len(float_cols):
        df[float_cols] = df[float_cols].astype("float32")
    return df


def _drop_embedded_header_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are the column header duplicated as literal data.

    A known, real quirk in multi-file exports (e.g. some CIC-IDS2018 raw
    day-files): the header row gets embedded partway through the file as
    an ordinary data row. Left in, it makes some chunks infer a
    different (object) dtype for an otherwise-numeric column than other
    chunks do, which crashes reservoir_sample's cross-chunk assignment
    with a LossySetitemError - a real failure hit against real data, not
    a hypothetical. Schema-agnostic: flags a row only when EVERY column's
    value equals that column's own name, so it can't false-positive on
    a legitimate row that happens to match one header string.
    """
    mask = (df.astype(str) == df.columns.astype(str)).all(axis=1)
    if mask.any():
        logger.warning("Dropped %d embedded header row(s) found as literal data", int(mask.sum()))
        df = df.loc[~mask]
    return df


def _is_parquet(path: str) -> bool:
    return str(path).lower().endswith(".parquet")


def _iter_raw_chunks(path: str, chunk_size: int | None) -> Iterator[pd.DataFrame]:
    """One file's chunks, dispatched by extension.

    CSV (plain or with a compression suffix pandas already infers from
    the name - .gz, .bz2, .zip [single member], .xz) via pd.read_csv,
    chunksize supported natively. Parquet via pyarrow's own batched
    reader, since pd.read_parquet has no chunksize equivalent; already
    a hard dependency (used for output.format: parquet), so this adds
    no new package to install.
    """
    if _is_parquet(path):
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        if chunk_size:
            for batch in parquet_file.iter_batches(batch_size=chunk_size):
                yield batch.to_pandas()
        else:
            yield parquet_file.read().to_pandas()
        return
    reader = pd.read_csv(path, chunksize=chunk_size, low_memory=False) if chunk_size \
        else [pd.read_csv(path, low_memory=False)]
    yield from reader


def iter_chunks(paths: list[str], chunk_size: int | None) -> Iterator[pd.DataFrame]:
    """Yield chunks with a dtype schema stable across the whole stream.

    pandas infers dtype independently per chunk of a chunked CSV read -
    a column that is int64 in one chunk can come out object in another
    purely from chunk-local quirks (a stray NaN, an unusual value only
    present in that chunk), with no embedded-header-row or other
    "real" data-quality issue involved. Real failure hit against
    CIC-IDS2018: this crashed reservoir_sample's cross-chunk assignment
    with a LossySetitemError. Fix: lock in which columns are numeric
    from the first chunk seen, then force every later chunk (including
    chunks from later files, for a multi-file raw_files list) through
    pd.to_numeric(errors="coerce") on exactly those columns, so the
    dtype is stable across the entire stream regardless of per-chunk
    inference quirks. Matches the IDS project's own loader, which does
    the same coercion for the same reason. Non-numeric columns are left
    alone. Known limitation: trusts the first chunk's inference: a
    column that's genuinely numeric but happens to look non-numeric in
    just the first chunk would be (wrongly) treated as categorical for
    the rest of the stream.
    """
    numeric_columns = None
    reference_columns = None
    for path in paths:
        for chunk in _iter_raw_chunks(path, chunk_size):
            chunk.columns = chunk.columns.str.strip()
            chunk = _drop_embedded_header_rows(chunk)

            if reference_columns is None:
                reference_columns = chunk.columns
            elif not chunk.columns.equals(reference_columns):
                # Real quirk hit against CIC-IDS2018: one raw day-file out of
                # ten carries 4 extra columns (Flow ID/Src IP/Src Port/Dst IP)
                # no other file has. Reservoir_sample's positional cross-chunk
                # assignment requires every chunk to share one fixed column
                # set, so align to whichever schema was seen first - extra
                # columns are dropped, missing ones filled NaN - rather than
                # crashing or silently misaligning columns by position.
                extra = set(chunk.columns) - set(reference_columns)
                missing = set(reference_columns) - set(chunk.columns)
                logger.warning(
                    "%s: column schema differs from the first file read (extra: %s, "
                    "missing: %s) - aligning to the first file's schema",
                    path, sorted(extra), sorted(missing),
                )
                chunk = chunk.reindex(columns=reference_columns)

            if numeric_columns is None:
                numeric_columns = chunk.select_dtypes(include=["number"]).columns
            for col in numeric_columns:
                if col in chunk.columns:
                    # Always land on float64 here, never int64: an int64
                    # column in one chunk (e.g. a 0/1 flag column with no
                    # NaN in that particular chunk) and a float64 version
                    # of the same column in another (NaN introduced by
                    # coercion, or genuinely fractional values) hits the
                    # same LossySetitemError this whole schema-locking
                    # exists to prevent - real failure, CIC-IDS2018.
                    chunk[col] = pd.to_numeric(chunk[col], errors="coerce").astype("float64")
            yield _downcast_chunk(chunk)


def reservoir_sample(chunks: Iterator[pd.DataFrame], max_rows: int, seed: int = 0) -> tuple[pd.DataFrame, int]:
    """Uniform reservoir sample of at most max_rows rows across all chunks.

    Vectorized batched Algorithm R: within a chunk, later rows correctly
    overwrite earlier rows at the same reservoir slot (pandas/numpy
    fancy-indexing assignment resolves duplicate target positions by
    keeping the last one in source order), matching the sequential
    semantics of the classic single-item algorithm.
    """
    rng = np.random.default_rng(seed)
    reservoir: pd.DataFrame | None = None
    n_seen = 0

    for chunk in chunks:
        if reservoir is None:
            reservoir = chunk.iloc[0:0].copy()

        if n_seen < max_rows:
            take = min(max_rows - n_seen, len(chunk))
            reservoir = pd.concat([reservoir, chunk.iloc[:take]], ignore_index=True)
            chunk = chunk.iloc[take:]
            n_seen += take

        m = len(chunk)
        if m > 0:
            global_idx = np.arange(n_seen, n_seen + m)
            j = rng.integers(0, global_idx + 1)  # per-row draw in [0, i], inclusive
            replace_mask = j < max_rows
            if replace_mask.any():
                reservoir.iloc[j[replace_mask]] = chunk.iloc[np.flatnonzero(replace_mask)].values
            n_seen += m

    if reservoir is None:
        raise ValueError("No data read, chunk source was empty")
    return reservoir, n_seen


def load_file(path: str, chunk_size: int | None, max_rows: int | None, seed: int = 0) -> pd.DataFrame:
    chunks = iter_chunks([path], chunk_size)
    if max_rows:
        df, n_seen = reservoir_sample(chunks, max_rows, seed)
        logger.info("Reservoir-sampled %s: %d rows seen -> %d kept (dataset.max_rows)", path, n_seen, len(df))
        return df
    return pd.concat(list(chunks), ignore_index=True)


def load_files_combined(paths: list[str], chunk_size: int | None, max_rows: int | None, seed: int = 0) -> pd.DataFrame:
    chunks = iter_chunks(paths, chunk_size)
    if max_rows:
        df, n_seen = reservoir_sample(chunks, max_rows, seed)
        logger.info("Reservoir-sampled %d files: %d rows seen -> %d kept (dataset.max_rows)", len(paths), n_seen, len(df))
        return df
    return pd.concat(list(chunks), ignore_index=True)
