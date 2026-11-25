#!/usr/bin/env python3
"""Coverage of homogeneity_test's intervals when rows are clustered by host.

homogeneity_coverage.py studied repeated feature vectors. Here the dependence
comes from hosts: every row belongs to a host, a host repeats a few vectors of
its own (its typical flows) and occasionally sends a new one, and host sizes
vary widely. Rows of one host are therefore dependent, and a random split puts
most hosts on both sides. The check runs as released, with
audit.homogeneity_cluster_columns: [host], so each class gets the default
Newcombe interval (row_ci_95) and the host-cluster bootstrap interval
(cluster_ci_95).

Each interval is judged against two estimands, as in Section 3.9:
  A  the realized difference: the two match rates over every row of the split
     being audited (what an audit is about)
  B  the generator difference: 0 without injected copies, otherwise the mean
     of A over the regime's simulations

Regimes (two classes, 3 sd apart):
  hosts_few    10 hosts per class, 5,000 rows per class
  hosts_many   100 hosts per class, 5,000 rows per class
each at split ratios 0.7, 0.8 and 0.9, plus
  hosts_few_leak10   hosts_few at 0.8 with 10% of each class's test rows
                     replaced by copies of training rows (copies keep their
                     source's host)

Usage: python3 validation/homogeneity_host_coverage.py [--sims N] [--jobs N] [--out PATH]
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fixtures import base_cfg  # noqa: E402
from homogeneity_coverage import full_rate_diff  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

from ids2eval.audit import homogeneity  # noqa: E402
from ids2eval.data import dataset  # noqa: E402

K = 6
ROWS = 5000
TEMPLATES = 8          # typical flows per host
FRESH = 0.3            # share of a host's rows that are new vectors
REGIMES = {}
for kind, hosts in (("hosts_few", 10), ("hosts_many", 100)):
    for ratio in (0.7, 0.8, 0.9):
        REGIMES[f"{kind}_{int(ratio * 100)}"] = {"hosts": hosts, "ratio": ratio}
REGIMES["hosts_few_leak10_80"] = {"hosts": 10, "ratio": 0.8, "leak": 0.10}
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "homogeneity_host_coverage.json"


def population(rng, hosts):
    parts = []
    for i, cls in enumerate(("benign", "attack")):
        sizes = rng.zipf(1.5, size=hosts).astype(float)
        host = rng.choice(hosts, size=ROWS, p=sizes / sizes.sum())
        templates = rng.normal(size=(hosts, TEMPLATES, K))
        fresh = rng.random(ROWS) < FRESH
        x = templates[host, rng.integers(0, TEMPLATES, ROWS)]
        x[fresh] = rng.normal(size=(int(fresh.sum()), K))
        df = pd.DataFrame(x + 3.0 * i, columns=[f"f{j}" for j in range(K)])
        df["host"] = [f"{cls}-{h}" for h in host]
        df["label"] = cls
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def one(name, spec, sim):
    rng = np.random.default_rng(20_000 * (list(REGIMES).index(name) + 1) + sim)
    pop = population(rng, spec["hosts"])
    train, test = dataset._random_split(pop, "label", {"split_ratio": spec["ratio"]}, seed=sim)
    if spec.get("leak"):
        for cls in ("benign", "attack"):
            idx = np.flatnonzero(test["label"].to_numpy() == cls)
            k = round(spec["leak"] * len(idx))
            pick = rng.choice(idx, k, replace=False)
            test.iloc[pick] = train[train["label"] == cls].sample(n=k, random_state=sim).to_numpy()
        test = test.infer_objects()
    cfg = base_cfg()
    cfg["schema"]["label_column"] = "label"
    cfg["schema"]["drop_columns"] = ["host"]
    cfg["audit"]["homogeneity_cluster_columns"] = ["host"]
    cfg["random_seed"] = sim
    per_class = homogeneity.check(train, test, cfg)["details"]["per_class"]
    full = full_rate_diff(train.drop(columns="host"), test.drop(columns="host"))
    return [{"regime": name, "sim": sim, "class": c, "full_diff": full[c],
             "row_ci": v["row_ci_95"], "cluster_ci": v["cluster_ci_95"],
             "row_class": v["classification"], "cluster_class": v["cluster_classification"],
             "test_hosts": int(test.loc[test["label"] == c, "host"].nunique())}
            for c, v in per_class.items()]


def summarize(rows, margin):
    out = {}
    for name, spec in REGIMES.items():
        rs = [r for r in rows if r["regime"] == name]
        if not rs:
            continue
        b = 0.0 if not spec.get("leak") else float(np.mean([r["full_diff"] for r in rs]))
        a = np.array([r["full_diff"] for r in rs])
        e = {"intervals": len(rs), "estimand_b": b, "mean_estimand_a": float(a.mean()),
             "sd_estimand_a": float(a.std(ddof=1)), "mean_test_hosts": float(np.mean([r["test_hosts"] for r in rs]))}
        for kind in ("row", "cluster"):
            lo = np.array([r[f"{kind}_ci"][0] for r in rs])
            hi = np.array([r[f"{kind}_ci"][1] for r in rs])
            cls = [r[f"{kind}_class"] for r in rs]
            e[kind] = {
                "coverage_a": float(np.mean((lo <= a) & (a <= hi))),
                "coverage_b": float(np.mean((lo <= b) & (b <= hi))),
                "mean_width": float(np.mean(hi - lo)),
                "excess_matching": float(np.mean([c == "excess_matching" for c in cls])),
                # a false call: excess matching where the realized excess is within the margin
                "false_excess": float(np.mean([c == "excess_matching" and x <= margin
                                               for c, x in zip(cls, a, strict=True)])),
                "inconclusive": float(np.mean([c == "inconclusive" for c in cls])),
                "cleared": float(np.mean([c in ("equivalent", "below_control") for c in cls])),
            }
        out[name] = e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    tasks = [(n, s, i) for n, s in REGIMES.items() for i in range(args.sims)]
    nested = Parallel(n_jobs=args.jobs, verbose=2)(delayed(one)(n, s, i) for n, s, i in tasks)
    rows = [r for part in nested for r in part]
    summary = summarize(rows, homogeneity.EQUIVALENCE_MARGIN)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"sims": args.sims, "summary": summary, "rows": rows}, default=float))
    for name, e in summary.items():
        print(f"{name:22s} B={e['estimand_b']:+.3f} A sd={e['sd_estimand_a']:.3f} hosts={e['mean_test_hosts']:.1f} | "
              + " | ".join(f"{k}: covA={e[k]['coverage_a']:.3f} covB={e[k]['coverage_b']:.3f} "
                           f"w={e[k]['mean_width']:.3f} falseX={e[k]['false_excess']:.3f} "
                           f"incl={e[k]['inconclusive']:.3f}" for k in ("row", "cluster")), flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
