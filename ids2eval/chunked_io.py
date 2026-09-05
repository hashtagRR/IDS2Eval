"""Chunked CSV reading with optional reservoir sampling.

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
  It operates at the row level — if dataset.split_mode is "grouped",
  sampling may fragment session groups across the sample boundary;
  that's a documented limitation, not a bug fix candidate for v1.
"""

from __future__ import annotations

import logging
from typing import Iterator

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _downcast_chunk(df: pd.DataFrame) -> pd.DataFrame:
    float_cols = df.select_dtypes(include=["float64"]).columns
    if len(float_cols):
        df[float_cols] = df[float_cols].astype("float32")
    return df


def iter_chunks(paths: list[str], chunk_size: int | None) -> Iterator[pd.DataFrame]:
    for path in paths:
        if chunk_size:
            for chunk in pd.read_csv(path, chunksize=chunk_size):
                chunk.columns = chunk.columns.str.strip()
                yield _downcast_chunk(chunk)
        else:
            df = pd.read_csv(path)
            df.columns = df.columns.str.strip()
            yield _downcast_chunk(df)


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
        raise ValueError("No data read — chunk source was empty")
    return reservoir, n_seen


def load_file(path: str, chunk_size: int | None, max_rows: int | None) -> pd.DataFrame:
    chunks = iter_chunks([path], chunk_size)
    if max_rows:
        df, n_seen = reservoir_sample(chunks, max_rows)
        logger.info("Reservoir-sampled %s: %d rows seen -> %d kept (dataset.max_rows)", path, n_seen, len(df))
        return df
    return pd.concat(list(chunks), ignore_index=True, copy=False)


def load_files_combined(paths: list[str], chunk_size: int | None, max_rows: int | None) -> pd.DataFrame:
    chunks = iter_chunks(paths, chunk_size)
    if max_rows:
        df, n_seen = reservoir_sample(chunks, max_rows)
        logger.info("Reservoir-sampled %d files: %d rows seen -> %d kept (dataset.max_rows)", len(paths), n_seen, len(df))
        return df
    return pd.concat(list(chunks), ignore_index=True, copy=False)
