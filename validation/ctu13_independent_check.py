#!/usr/bin/env python3
"""Independent recomputation of IDS2Eval's CTU-13 diagnostics (criterion S2).

Does not import IDS2Eval. Reads the prepared CTU-13 file with pandas, rebuilds
the random 80/20 split with scikit-learn's train_test_split under the same
arguments the audit uses (stratified on the label, seed 0), and recomputes:

  - training rows that repeat an earlier training row's feature vector
  - test rows whose feature vector occurs in training (counted over every
    test row, as dedup_check counts its leakage rows)
  - test rows that repeat another test row once those are removed
  - for each grouping key, the group count and the share of single-row groups
    over the whole file

Feature vectors use every column except the label, the attack category and
the columns the configuration drops, as the audit does. The numbers are then
compared with the audit's own report and every mismatch is listed.

Usage: python3 validation/ctu13_independent_check.py PREPARED_CSV_GZ RUN_DIR [RUN_DIR ...]
  each RUN_DIR is one audit run folder (with audit_report_before.json and
  resolved_config.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


def recompute(df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"], schema["attack_category_column"]}
    cols = [c for c in df.columns if c not in ignore]
    train, test = train_test_split(df, test_size=1.0 - cfg["dataset"]["split_ratio"],
                                   random_state=cfg["random_seed"], stratify=df[schema["label_column"]])
    train_dupes = int(train.duplicated(subset=cols).sum())
    train_unique = train[cols].drop_duplicates()
    reused = test.merge(train_unique, on=cols, how="left", indicator=True)["_merge"].eq("both").to_numpy()
    remaining = test[~reused]
    sizes = df.groupby(cfg["dataset"]["group_columns"], dropna=False, sort=False).size()
    return {
        "train_duplicates_dropped": train_dupes,
        "test_leakage_dropped": int(reused.sum()),
        "test_duplicates_dropped": int(remaining.duplicated(subset=cols).sum()),
        "groups": len(sizes),
        "singleton_group_share": float((sizes == 1).mean()),
    }


def reported(run_dir: Path) -> dict:
    findings = {f["check"]: f for f in json.loads((run_dir / "audit_report_before.json").read_text())}
    dedup = findings["dedup_check"]["details"]
    groups = findings["resplit_falsification"]["details"]["group_stats"]
    return {
        "train_duplicates_dropped": dedup["train_duplicates_dropped"],
        "test_leakage_dropped": dedup["test_leakage_dropped"],
        "test_duplicates_dropped": dedup["test_duplicates_dropped"],
        "groups": groups["groups"],
        "singleton_group_share": groups["singleton_group_share"],
    }


def main() -> None:
    data = pd.read_csv(sys.argv[1], low_memory=False)
    mismatches = 0
    for run in map(Path, sys.argv[2:]):
        cfg = json.loads((run / "resolved_config.json").read_text())
        mine, theirs = recompute(data, cfg), reported(run)
        for key, value in mine.items():
            same = abs(value - theirs[key]) < 1e-12 if isinstance(value, float) else value == theirs[key]
            mismatches += not same
            print(f"{run.name} {key}: independent={value} audit={theirs[key]} {'match' if same else 'MISMATCH'}")
    print("all match" if mismatches == 0 else f"{mismatches} mismatches")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
