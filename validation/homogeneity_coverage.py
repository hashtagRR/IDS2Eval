#!/usr/bin/env python3
"""Empirical coverage of homogeneity_test's interval under repeated vectors.

homogeneity_test puts a 95% Newcombe interval on the difference between two
match rates and treats every sampled row as an independent trial. Rows that
share a feature vector all match or all miss together, so the trials are
dependent whenever a class repeats vectors. This simulation measures what
that does to the interval: on populations with known structure it repeats
the whole draw-split-test cycle many times and counts how often the interval
covers the true difference, how often a class is wrongly called leakage, and
how often an injected leak is detected. The same draws are scored with the
cluster bootstrap of homogeneity_cluster.py (resampling whole vectors) for
comparison.

Populations (two classes each, random 80/20 split, so the true difference is
0 by symmetry unless test rows are injected):
  distinct      every row its own vector
  templates     50 vectors per class, drawn uniformly
  zipf          5,000 vectors per class with Zipf(1.3) frequencies
  mixed         half the rows distinct, half from 20 vectors per class
  mixed_small   as mixed with 150 rows per class (about 30 test rows)
  leak_05/10/20 mixed, then 5/10/20% of test rows replaced by copies of
                training rows; the true difference is estimated as the mean
                full-split rate difference over all simulations of the
                regime (every test and training row, not the 500-row samples)

Usage: venv/bin/python3 validation/homogeneity_coverage.py [--sims N] [--jobs N]
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import homogeneity_cluster as hc  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fixtures import base_cfg  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from sklearn.neighbors import NearestNeighbors  # noqa: E402

from ids2eval.data import dataset  # noqa: E402

hc.B = 1000
K = 6
ROWS = 2500
REGIMES = {
    "distinct": {}, "templates": {}, "zipf": {}, "mixed": {},
    "mixed_small": {"rows": 150},
    "leak_05": {"leak": 0.05}, "leak_10": {"leak": 0.10}, "leak_20": {"leak": 0.20},
}
MARGIN = hc.MARGIN
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "homogeneity_coverage.json"


def population(kind, rng, rows):
    parts = []
    for i, cls in enumerate(("benign", "attack")):
        if kind == "distinct":
            x = rng.normal(size=(rows, K))
        elif kind == "templates":
            x = rng.normal(size=(50, K))[rng.integers(0, 50, rows)]
        elif kind == "zipf":
            p = 1.0 / np.arange(1, 5001) ** 1.3
            x = rng.normal(size=(5000, K))[rng.choice(5000, rows, p=p / p.sum())]
        else:  # mixed
            half = rows // 2
            x = np.vstack([rng.normal(size=(half, K)),
                           rng.normal(size=(20, K))[rng.integers(0, 20, rows - half)]])
        df = pd.DataFrame(x + 3.0 * i, columns=[f"f{j}" for j in range(K)])
        df["label"] = cls
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def full_rate_diff(train, test):
    """Rate difference over every row, per class: the quantity the samples estimate."""
    cols = [c for c in train.columns if c != "label"]
    out = {}
    for cls in train["label"].unique():
        tr = train.loc[train["label"] == cls, cols].to_numpy()
        te = test.loc[test["label"] == cls, cols].to_numpy()
        # the check's index holds every class; a nearest neighbour from another
        # class is never within 1e-6 here (classes are 3 sd apart), so a
        # per-class index gives the same matches
        mu, sd = tr.mean(0), tr.std(0) + 1e-12
        nn = NearestNeighbors(n_neighbors=2).fit((tr - mu) / sd)
        t = nn.kneighbors((te - mu) / sd, n_neighbors=1)[0][:, 0] < 1e-6
        c = nn.kneighbors((tr - mu) / sd, n_neighbors=2)[0][:, 1] < 1e-6
        out[cls] = float(t.mean() - c.mean())
    return out


def one(name, spec, sim):
    rng = np.random.default_rng(10_000 * (list(REGIMES).index(name) + 1) + sim)
    kind = "mixed" if name.startswith("leak") or name == "mixed_small" else name
    pop = population(kind, rng, spec.get("rows", ROWS))
    train, test = dataset._random_split(pop, "label", {"split_ratio": 0.8}, seed=sim)
    if spec.get("leak"):
        for cls in ("benign", "attack"):
            idx = np.flatnonzero(test["label"].to_numpy() == cls)
            k = int(round(spec["leak"] * len(idx)))
            pick = rng.choice(idx, k, replace=False)
            src = train[train["label"] == cls].sample(n=k, random_state=sim)
            test.iloc[pick] = src.to_numpy()
        test = test.infer_objects()
    cfg = base_cfg()
    cfg["random_seed"] = sim
    res = hc.analyse(train, test, cfg, np.random.default_rng(sim))
    full = full_rate_diff(train, test)
    return [{"regime": name, "sim": sim, "class": c, "full_diff": full[c], **r} for c, r in res.items()]


def summarize(rows):
    out = {}
    for name in REGIMES:
        rs = [r for r in rows if r["regime"] == name]
        if not rs:
            continue
        truth = 0.0 if not REGIMES[name].get("leak") else float(np.mean([r["full_diff"] for r in rs]))
        e = {"intervals": len(rs), "truth": truth,
             "mean_test_rate": float(np.mean([r["test_rate"] for r in rs])),
             "mean_vectors_per_500": float(np.mean([r["test_vectors"] for r in rs]))}
        for kind in ("row", "cluster"):
            lo = np.array([r[f"{kind}_ci"][0] for r in rs])
            hi = np.array([r[f"{kind}_ci"][1] for r in rs])
            cls = [r[f"{kind}_class"] for r in rs]
            e[kind] = {"coverage": float(np.mean((lo <= truth) & (truth <= hi))),
                       "mean_width": float(np.mean(hi - lo)),
                       "leakage": float(np.mean([c == "leakage" for c in cls])),
                       "cleared": float(np.mean([c == "cleared" for c in cls])),
                       "inconclusive": float(np.mean([c == "inconclusive" for c in cls]))}
        out[name] = e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=500)
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    tasks = [(n, s, i) for n, s in REGIMES.items() for i in range(args.sims)]
    nested = Parallel(n_jobs=args.jobs, verbose=2)(delayed(one)(n, s, i) for n, s, i in tasks)
    rows = [r for part in nested for r in part]
    summary = summarize(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"sims": args.sims, "margin": MARGIN, "bootstrap": hc.B,
                                          "summary": summary, "rows": rows}, default=float))
    for name, e in summary.items():
        print(f"{name:12s} truth={e['truth']:+.4f} rate={e['mean_test_rate']:.2f} "
              f"vec/500={e['mean_vectors_per_500']:.0f} "
              f"row cov={e['row']['coverage']:.3f} w={e['row']['mean_width']:.3f} "
              f"leak={e['row']['leakage']:.3f} incl={e['row']['inconclusive']:.3f} | "
              f"cluster cov={e['cluster']['coverage']:.3f} w={e['cluster']['mean_width']:.3f} "
              f"leak={e['cluster']['leakage']:.3f} incl={e['cluster']['inconclusive']:.3f}", flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
