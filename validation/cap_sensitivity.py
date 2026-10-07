#!/usr/bin/env python3
"""Does the 200,000-row training cap change the random-vs-grouped delta?

For each seed, builds the same random and grouped splits the falsification
checks build, and fits the reference model (100-tree RandomForest, seed-driven
row sample and random_state, as in _fit_score) on 200K rows, 1M rows and the
whole training partition, always scoring the full test set. Reports, per cap,
the random-minus-grouped drop in accuracy, balanced accuracy and macro-F1 with
a paired Student-t interval over seeds. Every (seed, split, cap) result is
checkpointed, so an interrupted run resumes where it stopped.

Usage: venv/bin/python3 validation/cap_sensitivity.py NAME N_SEEDS [CAP ...] [--config PATH] [--out PATH]
       CAP is a row count or "full" (default: 200000 1000000 full); --config
       defaults to the local configs folder, --out to results/analysis/.
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

from class_sensitive_seeds import CONFIG_DIR, t_ci  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score  # noqa: E402

from ids2eval.config import load_config  # noqa: E402
from ids2eval.data import dataset, features  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "cap_sensitivity.json"
METRICS = ["accuracy", "balanced_accuracy", "macro_f1"]


def fit_score(train_df, test_df, label, cfg, seed, cap):
    cols = features.feature_columns(train_df, cfg)
    fit = train_df if cap == "full" or cap >= len(train_df) else train_df.sample(n=cap, random_state=seed)
    x_fit, x_test = features.encode_aligned(fit, test_df, cols, unseen="missing")
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_fit, fit[label])
    y_pred = clf.predict(x_test)
    y = test_df[label]
    return {"accuracy": float(accuracy_score(y, y_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, y_pred)),
            "macro_f1": float(f1_score(y, y_pred, average="macro", zero_division=0)),
            "fit_rows": len(fit)}


def summarize(entry, caps):
    out = {}
    for cap in caps:
        key = str(cap)
        pairs = [s for s in entry["seeds"].values() if key in s.get("random", {}) and key in s.get("grouped", {})]
        if not pairs:
            continue
        out[key] = {"n_seeds": len(pairs)}
        for m in METRICS:
            out[key][m] = dict(zip(["mean_drop", "ci_low", "ci_high"],
                                   t_ci([p["random"][key][m] - p["grouped"][key][m] for p in pairs]), strict=True))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("n_seeds", type=int)
    ap.add_argument("caps", nargs="*", default=["200000", "1000000", "full"])
    ap.add_argument("--config")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    name, n_seeds, out = args.name, args.n_seeds, args.out
    caps = [c if c == "full" else int(c) for c in args.caps]
    results = json.loads(out.read_text()) if out.exists() else {}
    entry = results.setdefault(name, {"seeds": {}})
    cfg = load_config(args.config or str(CONFIG_DIR / f"{name}.yaml"))
    label = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
    print(f"=== {name}: {len(combined):,} rows, caps {caps}", flush=True)
    for seed in range(n_seeds):
        rec = entry["seeds"].setdefault(str(seed), {"random": {}, "grouped": {}})
        for split_name, splitter in (("random", dataset._random_split), ("grouped", dataset._grouped_split)):
            todo = [c for c in caps if str(c) not in rec[split_name]]
            if not todo:
                continue
            train_df, test_df = splitter(combined, label, cfg["dataset"], seed=seed)
            for cap in todo:
                t0 = time.time()
                rec[split_name][str(cap)] = fit_score(train_df, test_df, label, cfg, seed, cap)
                rec[split_name][str(cap)]["seconds"] = round(time.time() - t0, 1)
                entry["summary"] = summarize(entry, caps)
                out.write_text(json.dumps(results, indent=2))
                r = rec[split_name][str(cap)]
                print(f"  seed {seed} {split_name} cap {cap}: acc {r['accuracy']:.5f} macroF1 {r['macro_f1']:.4f} "
                      f"({r['fit_rows']:,} rows, {r['seconds']:.0f}s)", flush=True)
            del train_df, test_df
            gc.collect()
    for cap, s in summarize(entry, caps).items():
        print(f"cap {cap}: " + "; ".join(f"{m} drop {s[m]['mean_drop']:+.5f} [{s[m]['ci_low']}, {s[m]['ci_high']}]"
                                         for m in METRICS), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
