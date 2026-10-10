#!/usr/bin/env python3
"""Host-disjoint cross-validation: source-host and destination-host holdouts.

The paper's grouped resplits keep each 5-tuple on one side of the split.
A 5-tuple split still lets one host appear on both sides, so a model can
learn a host's traffic in training and meet the same host at test time.
This compares a random split with splits in which every source host (or
every destination host) sits on one side only.

Design. A single held-out fold does not work here. With a few dozen hosts of
very uneven size, StratifiedGroupKFold puts the same hosts in its first fold
for every shuffle seed (on ToN-IoT's source IPs, identically for seeds 0-4),
so repeated seeds would only measure model noise. And a host-disjoint fold
changes the test-set class mix, which makes its accuracy incomparable with a
random fold's (the confound Section 6.4 of the paper discusses). So both
designs are run as 5-fold cross-validation: StratifiedKFold for the random
split, StratifiedGroupKFold over one IP column for the host-disjoint split
(the splitter the tool's grouped split uses, with every fold used once).
Every row is then predicted exactly once out of fold in both designs, and
the metrics are computed on the pooled out-of-fold predictions of the same
rows, with the same class mix.

Each fold is fit with the frozen tool's reference model (100-tree random
forest on at most 200,000 training rows, unseen categories as missing), twice:
with the identifier columns kept, as the tool's default feature set does, and
with them dropped. A test row whose class has no training rows in its fold
cannot be predicted correctly; the script counts these rows, since a class
confined to a few hosts is itself what a host holdout can reveal.

Usage: venv/bin/python3 validation/host_holdout.py NAME:N_REPEATS [NAME:N_REPEATS ...]
"""
from __future__ import annotations

import copy
import gc
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

from ids2eval.config import load_config
from ids2eval.data import dataset, features

MAX_FIT_ROWS = 200_000  # matches ids2eval.audit._fit_score.MAX_FIT_ROWS
N_FOLDS = 5  # split_ratio 0.8, as in the tool's grouped split
CONFIG_DIR = Path(__file__).resolve().parent.parent / "results" / "configs"  # raw_files is overridden below
DATA = Path(os.environ.get("IDS2EVAL_DATA", "/home/tango/projects/IDS2Eval_data"))  # data root; set on Batch
OUT_PATH = Path(__file__).resolve().parent.parent / "results" / "analysis" / "host_holdout.json"

DATASETS = {
    "ton-iot-official": {"raw": DATA / "ton-iot-official/train_test_network.csv.gz",
                         "hosts": {"source_host": "src_ip", "destination_host": "dst_ip"}},
    "bot-iot-official": {"raw": DATA / "bot-iot-official/bot-iot-all-features.parquet",
                         "hosts": {"source_host": "saddr", "destination_host": "daddr"}},
}
VARIANTS = ("ids_kept", "ids_dropped")


def fold_predict(df, train_idx, test_idx, label_col, cfg, seed, drop_ids):
    run_cfg = copy.deepcopy(cfg)
    if drop_ids:
        run_cfg["schema"]["drop_columns"] = list(run_cfg["schema"]["drop_columns"]) + list(
            run_cfg["schema"].get("id_like_columns") or [])
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]
    cols = features.feature_columns(train_df, run_cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols, unseen="missing")
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])
    return clf.predict(x_test)


def metrics(y_true, y_pred, unpredictable):
    labels = sorted(np.unique(y_true))
    recalls = recall_score(y_true, y_pred, average=None, labels=labels, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)),
        "per_class_recall": {str(c): float(r) for c, r in zip(labels, recalls, strict=True)},
        "rows_whose_class_had_no_training_rows": int(unpredictable.sum()),
        "per_class_rows_without_training_rows": {
            str(c): int((unpredictable & (y_true == c)).sum()) for c in labels},
    }


def cross_validate(df, label_col, cfg, splitter, groups, seed):
    y = df[label_col].to_numpy()
    preds = {v: np.empty(len(df), dtype=object) for v in VARIANTS}
    unpredictable = np.zeros(len(df), dtype=bool)
    folds = []
    for train_idx, test_idx in splitter.split(df, y, groups):
        missing = set(np.unique(y[test_idx])) - set(np.unique(y[train_idx]))
        unpredictable[test_idx] = np.isin(y[test_idx], list(missing))
        if groups is not None:
            overlap = set(groups[train_idx]) & set(groups[test_idx])
            if overlap:
                raise RuntimeError(f"{len(overlap)} hosts on both sides of a fold")
        for v in VARIANTS:
            preds[v][test_idx] = fold_predict(df, train_idx, test_idx, label_col, cfg, seed, v == "ids_dropped")
        folds.append({"test_rows": int(len(test_idx)),
                      "test_hosts": None if groups is None else int(len(set(groups[test_idx]))),
                      "classes_without_training_rows": sorted(str(c) for c in missing)})
        gc.collect()
    return {"folds": folds, **{v: metrics(y, preds[v].astype(y.dtype), unpredictable) for v in VARIANTS}}


def main():
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    for arg in sys.argv[1:]:
        name, n_repeats = arg.split(":")
        n_repeats = int(n_repeats)
        spec = DATASETS[name]
        cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
        cfg["dataset"]["raw_files"] = [str(spec["raw"])]
        label_col = cfg["schema"]["label_column"]
        entry = results.setdefault(name, {"repeats": []})
        done = len(entry["repeats"])
        if done >= n_repeats:
            continue
        df = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"]).reset_index(drop=True)
        entry["rows"] = int(len(df))
        print(f"=== {name}: {len(df):,} rows, repeats {done}..{n_repeats - 1}", flush=True)
        for seed in range(done, n_repeats):
            row = {"seed": seed, "random": cross_validate(
                df, label_col, cfg, StratifiedKFold(N_FOLDS, shuffle=True, random_state=seed), None, seed)}
            for key, col in spec["hosts"].items():
                groups = df[col].astype(str).to_numpy()
                row[key] = cross_validate(
                    df, label_col, cfg, StratifiedGroupKFold(N_FOLDS, shuffle=True, random_state=seed), groups, seed)
                r, g = row["random"]["ids_dropped"], row[key]["ids_dropped"]
                print(f"  repeat {seed} {key} (ids dropped): accuracy {r['accuracy']:.4f} -> {g['accuracy']:.4f}, "
                      f"balanced {r['balanced_accuracy']:.4f} -> {g['balanced_accuracy']:.4f}, "
                      f"rows with untrained class {g['rows_whose_class_had_no_training_rows']:,}", flush=True)
            entry["repeats"].append(row)
            OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUT_PATH.write_text(json.dumps(results, indent=2))
        del df
        gc.collect()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
