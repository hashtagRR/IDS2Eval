#!/usr/bin/env python3
"""Cluster-aware sensitivity for homogeneity_test's intervals.

homogeneity_test treats its (up to) 500 sampled rows per arm as independent
trials. Rows that share one encoded feature vector are not independent: they
have the same nearest-neighbour distance, so they all match or all miss. This
script re-draws exactly the samples homogeneity.check draws (same index
sample, same per-class RandomState(0) draws, same scaling and 1e-6 cutoff),
groups each arm's sampled rows by their encoded feature vector, and computes
a 95% percentile bootstrap interval on the rate difference that resamples
whole vectors instead of rows. Each class is then classified as homogeneity
.check does (leakage / cleared / inconclusive against the +0.05 margin) under
both intervals, and changes are listed.

After deduplication every sampled row is its own vector (dedup removes
repeated vectors within and across splits), so the two intervals can differ
only before deduplication; the after-stage is computed as a check of that.

Usage: venv/bin/python3 validation/homogeneity_cluster.py [NAME ...]
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
DATA = Path("/home/tango/projects/IDS2Eval_data")
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "homogeneity_cluster.json"
MARGIN = 0.05
B = 4000


def classify(lo, hi):
    if lo > MARGIN:
        return "leakage"
    if hi < MARGIN:
        return "cleared"
    return "inconclusive"


def samples(train_df, test_df, cfg):
    """Per class: (test match flags, test vector ids, control match flags, control vector ids)."""
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
        t_match = nn.kneighbors(x_test[t_idx], n_neighbors=1)[0][:, 0] < h.NEAR_ZERO_DISTANCE
        c_match = nn.kneighbors(x_index[c_idx], n_neighbors=2)[0][:, 1] < h.NEAR_ZERO_DISTANCE
        t_vec = pd.util.hash_pandas_object(x_test_raw.iloc[t_idx], index=False).to_numpy()
        c_vec = pd.util.hash_pandas_object(x_index_raw.iloc[c_idx], index=False).to_numpy()
        out[str(cls)] = (t_match, t_vec, c_match, c_vec)
    return out


def clusters(match, vec):
    """Cluster sizes and their match indicator (rows sharing a vector match alike)."""
    _, inv, sizes = np.unique(vec, return_inverse=True, return_counts=True)
    hits = np.bincount(inv, weights=match.astype(float))
    return sizes.astype(float), hits


def boot_rate(sizes, hits, rng):
    draw = rng.multinomial(len(sizes), np.full(len(sizes), 1 / len(sizes)), size=B)
    return (draw @ hits) / (draw @ sizes)


def analyse(train_df, test_df, cfg, rng):
    res = {}
    for cls, (t_match, t_vec, c_match, c_vec) in samples(train_df, test_df, cfg).items():
        p_t, p_c = float(t_match.mean()), float(c_match.mean())
        lo, hi = h._rate_diff_ci(p_t, len(t_match), p_c, len(c_match))
        ts, th = clusters(t_match, t_vec)
        cs, ch = clusters(c_match, c_vec)
        diff = boot_rate(ts, th, rng) - boot_rate(cs, ch, rng)
        blo, bhi = (float(x) for x in np.percentile(diff, [2.5, 97.5]))
        res[cls] = {"test_rate": p_t, "control_rate": p_c, "n_test": len(t_match), "n_control": len(c_match),
                    "test_vectors": len(ts), "control_vectors": len(cs),
                    "row_ci": [lo, hi], "row_class": classify(lo, hi),
                    "cluster_ci": [blo, bhi], "cluster_class": classify(blo, bhi)}
    return res


def main():
    names = sys.argv[1:] or DATASETS
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    rng = np.random.default_rng(0)
    for name in names:
        cfg = load_config(str(DATA / "configs" / f"{name}.yaml"))
        cache = DATA / "output" / name / ".cache"
        tr, te = pd.read_parquet(cache / "train.parquet"), pd.read_parquet(cache / "test.parquet")
        for stage in ("before", "after"):
            if stage == "after":
                tr, te, _ = dataset.dedup(tr, te, cfg)
            res = analyse(tr, te, cfg, rng)
            results[f"{name}/{stage}"] = res
            OUT.write_text(json.dumps(results, indent=2))
            changed = {c: f"{r['row_class']}->{r['cluster_class']}" for c, r in res.items()
                       if r["row_class"] != r["cluster_class"]}
            dup = {c: f"{r['test_vectors']}/{r['n_test']}, {r['control_vectors']}/{r['n_control']}" for c, r in res.items()
                   if r["test_vectors"] < r["n_test"] or r["control_vectors"] < r["n_control"]}
            print(f"{name}/{stage}: {len(res)} classes; row-level "
                  f"{dict(pd.Series([r['row_class'] for r in res.values()]).value_counts())}; "
                  f"changed: {changed or 'none'}; classes with repeated vectors (test, control): {len(dup)}",
                  flush=True)
        del tr, te
        gc.collect()
    print("DONE")


if __name__ == "__main__":
    main()
