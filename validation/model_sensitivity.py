#!/usr/bin/env python3
"""Is the random-vs-grouped null a RandomForest artifact?

Repeats class_sensitive_seeds.py's paired-seed comparison with two other
model families, LogisticRegression (standardized features) and XGBoost,
using the same splits, the same 200,000-row training cap and the same
seeds, so the RandomForest results already in class_sensitive_seeds.json
form the third arm. Results are checkpointed after every seed.

Usage: venv/bin/python3 validation/model_sensitivity.py NAME:N_SEEDS [NAME:N_SEEDS ...]
"""
from __future__ import annotations

import gc
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
from class_sensitive_seeds import CONFIG_DIR, MAX_FIT_ROWS, t_ci  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from ids2eval.config import load_config  # noqa: E402
from ids2eval.data import dataset, features  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "model_sensitivity.json"
METRICS = ["accuracy", "balanced_accuracy", "macro_f1"]


def models(seed: int, n_classes: int) -> dict:
    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "xgboost": XGBClassifier(n_estimators=100, max_depth=8, learning_rate=0.1, tree_method="hist",
                                 n_jobs=-1, random_state=seed,
                                 objective="multi:softprob" if n_classes > 2 else "binary:logistic"),
    }


def score_all(train_df, test_df, label_col, cfg, seed) -> dict:
    cols = features.feature_columns(train_df, cfg)
    fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_fit, x_test = features.encode_aligned(fit, test_df, cols)
    x_fit, x_test = x_fit.astype("float32").fillna(0), x_test.astype("float32").fillna(0)
    x_fit[~np.isfinite(x_fit)] = 0
    x_test[~np.isfinite(x_test)] = 0
    classes = np.array(sorted(fit[label_col].astype(str).unique()))
    index = {c: i for i, c in enumerate(classes)}
    y_fit = fit[label_col].astype(str).map(index).to_numpy()
    y_true = test_df[label_col].astype(str).map(index).fillna(-1).to_numpy().astype(int)
    out = {}
    for name, clf in models(seed, len(classes)).items():
        clf.fit(x_fit, y_fit)
        y_pred = np.asarray(clf.predict(x_test)).astype(int)
        out[name] = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
            "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        }
    return out


def summarize(seeds: list[dict]) -> dict:
    out = {"n_seeds": len(seeds)}
    for name in seeds[0]["random"]:
        out[name] = {m: dict(zip(["mean_drop", "ci_low", "ci_high"],
                                 t_ci([s["random"][name][m] - s["grouped"][name][m] for s in seeds]), strict=True))
                     for m in METRICS}
    return out


def main() -> None:
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for arg in sys.argv[1:]:
        name, n_seeds = arg.split(":")
        n_seeds = int(n_seeds)
        entry = results.setdefault(name, {"seeds": []})
        done = len(entry["seeds"])
        if done >= n_seeds:
            continue
        cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
        label = cfg["schema"]["label_column"]
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        print(f"=== {name}: {len(combined):,} rows, seeds {done}..{n_seeds - 1}", flush=True)
        for seed in range(done, n_seeds):
            tr, te = dataset._random_split(combined, label, cfg["dataset"], seed=seed)
            random_m = score_all(tr, te, label, cfg, seed)
            del tr, te
            tr, te = dataset._grouped_split(combined, label, cfg["dataset"], seed=seed)
            grouped_m = score_all(tr, te, label, cfg, seed)
            del tr, te
            gc.collect()
            entry["seeds"].append({"seed": seed, "random": random_m, "grouped": grouped_m})
            entry["summary"] = summarize(entry["seeds"])
            OUT.write_text(json.dumps(results, indent=2))
            print(f"  seed {seed}: " + "; ".join(
                f"{m} acc {random_m[m]['accuracy']:.4f}->{grouped_m[m]['accuracy']:.4f} "
                f"mF1 {random_m[m]['macro_f1']:.3f}->{grouped_m[m]['macro_f1']:.3f}" for m in random_m), flush=True)
        del combined
        gc.collect()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
