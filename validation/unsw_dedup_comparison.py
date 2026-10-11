#!/usr/bin/env python3
"""UNSW-NB15 duplicate-record rates for the comparison with Al-Daweri et al. (2020) (paper Table 5).

Two comparisons over the official partitions (column `id` dropped):
  pre_fix   every remaining column, including `label` and `attack_cat` (the original
            deduplication, Section 4.3)
  post_fix  feature columns only (dedup_check's comparison)

For each: training rows that repeat an earlier training row; testing rows that repeat
another testing row (within the testing partition alone, the figure comparable to
Al-Daweri et al.'s); and testing rows dropped when rows matching a training row are
also counted. The last equals dedup_check's leakage plus test-internal duplicates.

The two CSVs are identified by row count (175,341 training, 82,332 testing), because
the copy analyzed in Section 4 has the two file names swapped; their SHA-256 must match
results/dataset_manifest.json.

Usage: python3 validation/unsw_dedup_comparison.py DATA_DIR OUT_JSON
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

TRAIN_ROWS, TEST_ROWS = 175_341, 82_332
SHA256 = {"bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa",
          "734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rates(train: pd.DataFrame, test: pd.DataFrame, cols: list[str]) -> dict:
    train_dup = int(train[cols].duplicated().sum())
    test_dup = int(test[cols].duplicated().sum())
    matched = len(test[cols].drop_duplicates().merge(train[cols].drop_duplicates(), on=cols))
    return {"columns_compared": len(cols),
            "train_duplicates": train_dup, "train_rate": train_dup / len(train),
            "test_within_duplicates": test_dup, "test_within_rate": test_dup / len(test),
            "test_within_or_matching_train": test_dup + matched,
            "test_within_or_matching_train_rate": (test_dup + matched) / len(test)}


def main() -> None:
    data_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = sorted(data_dir.glob("UNSW_NB15_*-set.csv"))
    hashes = {f.name: sha256(f) for f in files}
    assert set(hashes.values()) == SHA256, f"unexpected input files: {hashes}"
    frames = [pd.read_csv(f, encoding="utf-8-sig") for f in files]
    train = next(df for df in frames if len(df) == TRAIN_ROWS)
    test = next(df for df in frames if len(df) == TEST_ROWS)
    all_cols = [c for c in train.columns if c != "id"]
    features = [c for c in all_cols if c not in ("label", "attack_cat")]
    result = {"input_sha256": hashes, "train_rows": len(train), "test_rows": len(test),
              "pre_fix": rates(train, test, all_cols), "post_fix": rates(train, test, features)}
    out.write_text(json.dumps(result, indent=2) + "\n")
    for k in ("pre_fix", "post_fix"):
        r = result[k]
        print(f"{k}: train {r['train_rate']:.2%} ({r['train_duplicates']:,}); "
              f"test within {r['test_within_rate']:.2%} ({r['test_within_duplicates']:,}); "
              f"within or matching train {r['test_within_or_matching_train_rate']:.2%} "
              f"({r['test_within_or_matching_train']:,})")


if __name__ == "__main__":
    main()
