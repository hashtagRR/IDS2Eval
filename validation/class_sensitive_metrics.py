#!/usr/bin/env python3
"""Re-derives resplit_falsification's random-vs-grouped comparison with
class-sensitive metrics (balanced accuracy, macro-F1, worst-class recall),
not just accuracy, for the datasets small enough to run locally: ToN-IoT
and BoT-IoT (official artifacts) and CIC-IDS2017-GLF.

Addresses a real reviewer concern: accuracy can stay flat across random vs.
grouped splits while minority-class behavior moves a lot, since a dominant
class's performance alone can carry the aggregate number. This reuses the
actual dataset._random_split/_grouped_split/features.encode_aligned
functions (not a reimplementation) so the comparison is methodologically
identical to resplit_falsification's own, just with more metrics recorded
per fit.

Usage: venv/bin/python3 validation/class_sensitive_metrics.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score,
)

from ids2eval.config import load_config
from ids2eval.data import dataset, features

MAX_FIT_ROWS = 200_000  # matches ids2eval.audit._fit_score.MAX_FIT_ROWS exactly

DATASETS = {
    "ton-iot-official": "/home/tango/projects/IDS2Eval_data/configs/ton-iot-official.yaml",
    "bot-iot-official": "/home/tango/projects/IDS2Eval_data/configs/bot-iot-official.yaml",
    "cic-ids2017-glf": "/home/tango/projects/IDS2Eval_data/configs/cic-ids2017-glf.yaml",
}


def fit_and_score_full(train_df, test_df, label_col, cfg, seed):
    cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols)
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])
    y_pred = clf.predict(x_test)
    y_true = test_df[label_col]

    per_class_recall = recall_score(y_true, y_pred, average=None, labels=sorted(y_true.unique()), zero_division=0)
    labels_sorted = sorted(y_true.unique())
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "worst_class_recall": float(min(per_class_recall)) if len(per_class_recall) else None,
        "worst_class_label": str(labels_sorted[int(per_class_recall.argmin())]) if len(per_class_recall) else None,
    }


def main():
    results = {}
    for name, config_path in DATASETS.items():
        print(f"=== {name} ===")
        cfg = load_config(config_path)
        label_col = cfg["schema"]["label_column"]
        seed = cfg["random_seed"]

        combined = dataset.load_raw_combined(cfg["dataset"], seed=seed)
        print(f"  loaded {len(combined):,} rows")

        random_train, random_test = dataset._random_split(combined, label_col, cfg["dataset"], seed=seed)
        grouped_train, grouped_test = dataset._grouped_split(combined, label_col, cfg["dataset"], seed=seed)

        random_metrics = fit_and_score_full(random_train, random_test, label_col, cfg, seed)
        grouped_metrics = fit_and_score_full(grouped_train, grouped_test, label_col, cfg, seed)

        print(f"  random : {random_metrics}")
        print(f"  grouped: {grouped_metrics}")
        results[name] = {"random": random_metrics, "grouped": grouped_metrics}

    out_path = Path(__file__).resolve().parent / "class_sensitive_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
