#!/usr/bin/env python3
"""Threshold sensitivity for homogeneity_test: re-classifies every class at
several equivalence margins and near-zero distance cutoffs, using the same
sampling, scaling and nearest-neighbor index as homogeneity.check so only the
thresholds vary.

Usage: venv/bin/python3 validation/homogeneity_sensitivity.py
"""
from __future__ import annotations

import gc
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.neighbors import NearestNeighbors  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from ids2eval.audit import homogeneity as h  # noqa: E402
from ids2eval.config import load_config  # noqa: E402
from ids2eval.data import dataset, features  # noqa: E402

DATASETS = ["unsw-nb15", "nsl-kdd", "cic-ids2017", "cic-ddos2019", "ton-iot-official", "bot-iot-official"]
MARGINS = [0.025, 0.05, 0.10]
CUTOFFS = [1e-6, 1e-3, 1e-1]
DATA = Path("/home/tango/projects/IDS2Eval_data")


def classify(ci_low, ci_high, margin):
    if ci_low > margin:
        return "leakage"
    if ci_high < margin:
        return "cleared"
    return "inconclusive"


def distances(train_df, test_df, cfg):
    group_col = cfg["schema"]["attack_category_column"] or cfg["schema"]["label_column"]
    cols = features.feature_columns(train_df, cfg)
    index_df = train_df.sample(n=min(len(train_df), h.MAX_INDEX_ROWS), random_state=cfg["random_seed"])
    x_index_raw, x_test_raw = features.encode_aligned(index_df, test_df, cols)
    scaler = StandardScaler().fit(x_index_raw)
    x_index, x_test = scaler.transform(x_index_raw), scaler.transform(x_test_raw)
    nn = NearestNeighbors(n_neighbors=2, n_jobs=2).fit(x_index)
    out = {}
    for cls, count in train_df[group_col].value_counts().items():
        test_mask = test_df[group_col] == cls
        index_mask = (index_df[group_col] == cls).values
        if min(count, test_mask.sum(), index_mask.sum()) < h.MIN_CLASS_SIZE:
            continue
        t_idx = np.random.RandomState(0).choice(
            np.flatnonzero(test_mask.values), size=min(h.SAMPLE_SIZE, test_mask.sum()), replace=False)
        c_idx = np.random.RandomState(0).choice(
            np.flatnonzero(index_mask), size=min(h.SAMPLE_SIZE, index_mask.sum()), replace=False)
        out[str(cls)] = (nn.kneighbors(x_test[t_idx], n_neighbors=1)[0][:, 0],
                         nn.kneighbors(x_index[c_idx], n_neighbors=2)[0][:, 1])
    return out


def main():
    results = {}
    for name in DATASETS:
        cfg = load_config(str(DATA / "configs" / f"{name}.yaml"))
        cache = DATA / "output" / name / ".cache"
        tr, te = pd.read_parquet(cache / "train.parquet"), pd.read_parquet(cache / "test.parquet")
        for stage in ["before", "after"]:
            if stage == "after":
                tr, te, _ = dataset.dedup(tr, te, cfg)
            dists = distances(tr, te, cfg)
            baseline = {}
            for cls, (test_d, ctrl_d) in dists.items():
                p_t, p_c = float((test_d < 1e-6).mean()), float((ctrl_d < 1e-6).mean())
                lo, hi = h._rate_diff_ci(p_t, len(test_d), p_c, len(ctrl_d))
                baseline[cls] = {"test_rate": p_t, "control_rate": p_c, "n_test": len(test_d),
                                 "n_control": len(ctrl_d), "ci": [lo, hi], "class": classify(lo, hi, 0.05)}
            grid = {}
            for cutoff in CUTOFFS:
                for margin in MARGINS:
                    counts = {"leakage": 0, "cleared": 0, "inconclusive": 0}
                    for test_d, ctrl_d in dists.values():
                        p_t, p_c = float((test_d < cutoff).mean()), float((ctrl_d < cutoff).mean())
                        lo, hi = h._rate_diff_ci(p_t, len(test_d), p_c, len(ctrl_d))
                        counts[classify(lo, hi, margin)] += 1
                    grid[f"cutoff={cutoff:g},margin={margin:g}"] = counts
            results[f"{name}/{stage}"] = {"grid": grid, "baseline": baseline}
            print(name, stage, grid["cutoff=1e-06,margin=0.05"], flush=True)
        del tr, te
        gc.collect()
    out = Path(__file__).resolve().parent.parent / "results" / "analysis" / "homogeneity_sensitivity.json"
    out.write_text(json.dumps(results, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
