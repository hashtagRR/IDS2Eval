#!/usr/bin/env python3
"""Is the accuracy advantage of reused test rows a class-mix effect?

matched_vs_novel.py found that test rows whose exact feature vector also
appears in training ("reused") score higher than the other ("novel") test
rows on UNSW-NB15 and NSL-KDD. Reused rows may simply come from easier
classes. This script separates the two on the official partitions:

  raw advantage       accuracy on reused rows minus accuracy on novel rows,
                      and its weight in the headline accuracy (reused share
                      times the advantage, equal to overall accuracy minus
                      novel-row accuracy)
  class-adjusted      the same comparison within each stratum (UNSW-NB15:
                      attack_cat; NSL-KDD: the attack label), with novel-row
                      accuracy reweighted to the reused rows' stratum mix.
                      Strata with fewer than MIN_NOVEL novel rows cannot be
                      compared and are left out; the share of reused rows
                      covered is reported.

The model is the falsification checks' reference model (100-tree random
forest on at most 200,000 training rows, unseen categories as missing),
refit for seeds 0-4; the reused/novel split uses dedup_check's columns.
Intervals: 2,000 bootstrap draws of test rows within the reused and novel
groups, on the seed-0 predictions.

Usage: venv/bin/python3 validation/reuse_stratified.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ids2eval.config import load_config
from ids2eval.data import dataset, features

DATA = Path(os.environ.get("IDS2EVAL_DATA", "/home/tango/projects/IDS2Eval_data"))
CONFIG_DIR = Path(__file__).resolve().parent.parent / "results" / "configs"
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "reuse_stratified.json"
MAX_FIT_ROWS = 200_000
SEEDS = range(5)
MIN_NOVEL = 20
B = 2000

# the local UNSW-NB15 mirror's file names are inverted (paper Section 4.2): select by content
FILES = {
    "unsw-nb15": (DATA / "unsw-nb15/UNSW_NB15_testing-set.csv", DATA / "unsw-nb15/UNSW_NB15_training-set.csv",
                  "attack_cat", (175_341, 82_332)),
    "nsl-kdd": (DATA / "nsl-kdd/KDDTrain+.csv.gz", DATA / "nsl-kdd/KDDTest+.csv.gz", None, (125_973, 22_544)),
}


def load(name):
    train_file, test_file, stratum, sizes = FILES[name]
    cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
    cfg["dataset"]["train_file"], cfg["dataset"]["test_file"] = str(train_file), str(test_file)
    train, test = dataset.load_split(cfg)
    if (len(train), len(test)) != sizes:
        raise RuntimeError(f"{name}: unexpected partition sizes {len(train)}, {len(test)}")
    return cfg, train, test, stratum or cfg["schema"]["label_column"]


def reused_mask(train, test, cfg):
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    cols = [c for c in train.columns if c not in ignore]
    h_train = pd.util.hash_pandas_object(train[cols].astype(str), index=False)
    h_test = pd.util.hash_pandas_object(test[cols].astype(str), index=False)
    return h_test.isin(set(h_train)).to_numpy()


def predict_correct(train, test, cfg, seed):
    label = cfg["schema"]["label_column"]
    cols = features.feature_columns(train, cfg)
    fit = train.sample(n=min(len(train), MAX_FIT_ROWS), random_state=seed)
    x_fit, x_test = features.encode_aligned(fit, test, cols, unseen="missing")
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1).fit(x_fit, fit[label])
    return clf.predict(x_test) == test[label].to_numpy()


def adjusted(correct, reused, strata):
    """Class-adjusted advantage: reused accuracy minus novel accuracy reweighted to the reused mix."""
    df = pd.DataFrame({"ok": correct, "reused": reused, "s": strata})
    per = df.groupby(["s", "reused"])["ok"].agg(["mean", "size"]).unstack("reused")
    per.columns = [f"{a}_{'reused' if b else 'novel'}" for a, b in per.columns]
    per = per.fillna(0)
    usable = per[(per.get("size_novel", 0) >= MIN_NOVEL) & (per.get("size_reused", 0) > 0)]
    n_r = usable["size_reused"]
    if n_r.sum() == 0:
        return None
    w = n_r / n_r.sum()
    acc_r = float((usable["mean_reused"] * w).sum())
    acc_n_adj = float((usable["mean_novel"] * w).sum())
    return {"reused_accuracy": acc_r, "novel_accuracy_reweighted": acc_n_adj, "advantage": acc_r - acc_n_adj,
            "reused_rows_covered": int(n_r.sum()), "reused_rows_total": int(reused.sum()),
            "per_stratum": {str(s): {k: (float(v) if "mean" in k else int(v)) for k, v in row.items()}
                            for s, row in per.iterrows()}}


def summary(correct, reused, strata):
    share = float(reused.mean())
    raw = float(correct[reused].mean() - correct[~reused].mean())
    adj = adjusted(correct, reused, strata)
    out = {"reused_share": share, "accuracy_all": float(correct.mean()),
           "accuracy_reused": float(correct[reused].mean()), "accuracy_novel": float(correct[~reused].mean()),
           "raw_advantage": raw, "raw_contribution": share * raw}
    if adj:
        cov = adj["reused_rows_covered"] / len(correct)
        out.update({"adjusted": adj, "adjusted_advantage": adj["advantage"],
                    "adjusted_contribution": cov * adj["advantage"]})
    return out


def bootstrap(correct, reused, strata, rng):
    idx_r, idx_n = np.flatnonzero(reused), np.flatnonzero(~reused)
    raw, adj = [], []
    for _ in range(B):
        i = np.concatenate([rng.choice(idx_r, len(idx_r)), rng.choice(idx_n, len(idx_n))])
        c, r, s = correct[i], reused[i], strata[i]
        raw.append(c[r].mean() - c[~r].mean())
        a = adjusted(c, r, s)
        adj.append(a["advantage"] if a else np.nan)
    pct = lambda v: [float(x) for x in np.nanpercentile(v, [2.5, 97.5])]  # noqa: E731
    return {"raw_advantage_ci": pct(raw), "adjusted_advantage_ci": pct(adj)}


def main():
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    rng = np.random.default_rng(0)
    for name in FILES:
        if name in results:
            print(f"skip {name} (done)", flush=True)
            continue
        cfg, train, test, stratum = load(name)
        reused = reused_mask(train, test, cfg)
        strata = test[stratum].astype(str).str.strip().to_numpy()
        runs = []
        for seed in SEEDS:
            correct = predict_correct(train, test, cfg, seed)
            runs.append(summary(correct, reused, strata))
            if seed == 0:
                ci = bootstrap(correct, reused, strata, rng)
            print(f"{name} seed {seed}: raw {runs[-1]['raw_advantage']:+.4f} "
                  f"adjusted {runs[-1].get('adjusted_advantage', float('nan')):+.4f}", flush=True)
        keys = ("accuracy_all", "accuracy_reused", "accuracy_novel", "raw_advantage", "raw_contribution",
                "adjusted_advantage", "adjusted_contribution")
        results[name] = {"stratum": stratum, "test_rows": len(test), "reused_rows": int(reused.sum()),
                         "mean_over_seeds": {k: float(np.mean([r[k] for r in runs if k in r])) for k in keys},
                         "seed0_bootstrap": ci, "runs": runs}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2))
        print(name, json.dumps(results[name]["mean_over_seeds"]), json.dumps(ci), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
