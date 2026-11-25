#!/usr/bin/env python3
"""Grouping-key statistics for datasets too large to load at once.

Streams a config's raw files in chunks, reading only the key columns, hashes
each row's key, and reports per key the same statistics as the grouped checks
(group count, share of single-row groups, size quantiles, largest group's row
share) without holding the data in memory. Column names are stripped of
surrounding spaces, as the loader does.

With --sample-key and --sample-frac it also writes a group-preserving sample:
every row whose key (under that key) hashes into the kept fraction, so a group
is kept whole or not at all, and the grouped resplit can run on the sample.

Keys come from validation/grouping_keys.py's KEYS for the config.

Usage: python3 validation/large_group_stats.py CONFIG OUT_JSON
           [--sample-key NAME --sample-frac F --sample-out PATH.csv.gz]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grouping_keys import KEYS, config_path, load_analysis_config

CHUNK_ROWS = 1_000_000
HASH_BUCKETS = 1_000_000


def key_hash(chunk: pd.DataFrame, columns: list[str]) -> np.ndarray:
    return pd.util.hash_pandas_object(chunk[columns].astype(str), index=False).to_numpy()


def stats_from_sizes(sizes: np.ndarray, columns: list[str]) -> dict:
    rows = int(sizes.sum())
    singletons = int((sizes == 1).sum())
    q50, q90, q99 = np.percentile(sizes, [50, 90, 99])
    return {"group_columns": columns, "rows": rows, "groups": len(sizes),
            "rows_per_group": rows / len(sizes), "singleton_group_share": singletons / len(sizes),
            "rows_in_singleton_groups": singletons / rows, "size_median": float(q50),
            "size_p90": float(q90), "size_p99": float(q99), "size_max": int(sizes.max()),
            "largest_group_row_share": float(sizes.max() / rows)}


def chunks(files, usecols=None):
    for f in files:
        for chunk in pd.read_csv(f, chunksize=CHUNK_ROWS, low_memory=False):
            chunk.columns = chunk.columns.str.strip()
            yield chunk if usecols is None else chunk[usecols]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("out")
    ap.add_argument("--sample-key")
    ap.add_argument("--sample-frac", type=float)
    ap.add_argument("--sample-out")
    args = ap.parse_args()
    path = config_path(args.config)
    cfg = load_analysis_config(path)
    keys = KEYS[path.stem]
    files = cfg["dataset"]["raw_files"]
    needed = sorted({c for cols in keys.values() for c in cols})

    hashes = {name: [] for name in keys}
    for chunk in chunks(files, needed):
        for name, cols in keys.items():
            hashes[name].append(key_hash(chunk, cols))
        print("rows so far", sum(len(h) for h in hashes[next(iter(keys))]), flush=True)
    result = {"config": path.stem, "keys": {}}
    for name, cols in keys.items():
        _, sizes = np.unique(np.concatenate(hashes.pop(name)), return_counts=True)
        result["keys"][name] = stats_from_sizes(sizes, cols)
        print(name, json.dumps(result["keys"][name]), flush=True)

    if args.sample_key:
        cols = keys[args.sample_key]
        keep_below = int(args.sample_frac * HASH_BUCKETS)
        written = 0
        with gzip.open(args.sample_out, "wt", newline="") as out:
            for i, chunk in enumerate(chunks(files)):
                kept = chunk[key_hash(chunk, cols) % HASH_BUCKETS < keep_below]
                kept.to_csv(out, index=False, header=(i == 0))
                written += len(kept)
        result["sample"] = {"key": args.sample_key, "fraction": args.sample_frac, "rows": written,
                            "path": Path(args.sample_out).name}
        print("sample rows", written, flush=True)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
