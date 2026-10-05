#!/usr/bin/env python3
"""Repeated-seed version of class_sensitive_metrics.py.

Same pairing and CI as repeated_seed_falsification_check: each seed drives
both the random split, the StratifiedGroupKFold shuffle in the grouped split,
and the RandomForest, and the per-seed (random minus grouped) difference is
summarized as a mean with a Student-t 95% CI. Done here for balanced
accuracy, macro-F1, worst-class recall and per-class recall, not just
accuracy. Results are checkpointed after every seed.

Usage: venv/bin/python3 validation/class_sensitive_seeds.py NAME:N_SEEDS [NAME:N_SEEDS ...]
"""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score,
)

from ids2eval.config import load_config
from ids2eval.data import dataset, features

MAX_FIT_ROWS = 200_000  # matches ids2eval.audit._fit_score.MAX_FIT_ROWS
CONFIG_DIR = Path("/home/tango/projects/IDS2Eval_data/configs")
OUT_PATH = Path(__file__).resolve().parent.parent / "results" / "analysis" / "class_sensitive_seeds.json"
SUMMARY_METRICS = ["accuracy", "balanced_accuracy", "macro_f1", "worst_class_recall"]


def score(train_df, test_df, label_col, cfg, seed):
    cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols)
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])
    y_pred = clf.predict(x_test)
    y_true = test_df[label_col]
    labels = sorted(y_true.unique())
    recalls = recall_score(y_true, y_pred, average=None, labels=labels, zero_division=0)
    support = y_true.value_counts()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "worst_class_recall": float(recalls.min()),
        "worst_class_label": str(labels[int(recalls.argmin())]),
        "per_class_recall": {str(c): float(r) for c, r in zip(labels, recalls, strict=True)},
        "per_class_support": {str(c): int(support[c]) for c in labels},
    }


def t_ci(values):
    n = len(values)
    m = mean(values)
    if n < 2:
        return m, None, None
    half = stats.t.ppf(0.975, df=n - 1) * stdev(values) / n ** 0.5
    return m, m - half, m + half


def summarize(seeds):
    out = {"n_seeds": len(seeds)}
    for metric in SUMMARY_METRICS:
        out[metric] = dict(zip(
            ["mean_drop", "ci_low", "ci_high"],
            t_ci([s["random"][metric] - s["grouped"][metric] for s in seeds]),
            strict=True,
        ))
    classes = set(seeds[0]["random"]["per_class_recall"])
    for s in seeds:
        classes &= set(s["random"]["per_class_recall"]) & set(s["grouped"]["per_class_recall"])
    out["per_class_recall_drop"] = {
        c: dict(zip(["mean_drop", "ci_low", "ci_high"], t_ci(
            [s["random"]["per_class_recall"][c] - s["grouped"]["per_class_recall"][c] for s in seeds]
        ), strict=True))
        for c in sorted(classes)
    }
    return out


def main():
    results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    for arg in sys.argv[1:]:
        name, n_seeds = arg.split(":")
        n_seeds = int(n_seeds)
        entry = results.setdefault(name, {"seeds": []})
        done = len(entry["seeds"])
        if done >= n_seeds:
            continue
        cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
        label_col = cfg["schema"]["label_column"]
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        print(f"=== {name}: {len(combined):,} rows, seeds {done}..{n_seeds - 1}", flush=True)
        for seed in range(done, n_seeds):
            tr, te = dataset._random_split(combined, label_col, cfg["dataset"], seed=seed)
            random_m = score(tr, te, label_col, cfg, seed)
            del tr, te
            tr, te = dataset._grouped_split(combined, label_col, cfg["dataset"], seed=seed)
            grouped_m = score(tr, te, label_col, cfg, seed)
            del tr, te
            gc.collect()
            entry["seeds"].append({"seed": seed, "random": random_m, "grouped": grouped_m})
            entry["summary"] = summarize(entry["seeds"])
            OUT_PATH.write_text(json.dumps(results, indent=2))
            print(
                f"  seed {seed}: macro_f1 {random_m['macro_f1']:.4f} -> {grouped_m['macro_f1']:.4f}, "
                f"worst {random_m['worst_class_label']} {random_m['worst_class_recall']:.3f} -> "
                f"{grouped_m['worst_class_label']} {grouped_m['worst_class_recall']:.3f}",
                flush=True,
            )
        del combined
        gc.collect()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
