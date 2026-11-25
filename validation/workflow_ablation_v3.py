#!/usr/bin/env python3
"""Workflow ablation, third design: what the grouped resplit cannot do alone.

In workflow_ablation_v2.py's six scenarios the grouped resplit alone (D4)
decides as well as both interventions together (D2), because every corpus
carries a grouping key that links copied or related rows. This design keeps
the same corpora (same generators and seeds) and removes or breaks that key,
as real benchmarks often do:

  <scenario>_nokey    no usable grouping key: the official UNSW-NB15 and
                      NSL-KDD partitions ship without address or port
                      columns, so the grouped resplit cannot run
  <scenario>_randkey  a key that does not link copies to their originals:
                      every row gets its own 5-tuple, so a copied test row and
                      its training original fall in different groups and the
                      grouped split separates nothing

applied to presplit_hard (copied test rows inflate accuracy; truth material),
presplit_easy (copied rows on easy classes; truth not material) and
group_noisy (related rows vary, nothing is copied; truth material).

Rules per corpus, as in v2: D4 the grouped resplit alone, D5 the reuse
intervention alone, D2 both (material if either is material, not material if
every applicable one is not material, otherwise inconclusive), D3 gated by
dedup_check and homogeneity_test. An intervention that cannot run counts as
inconclusive for a rule that relies on it alone.

Usage: python3 validation/workflow_ablation_v3.py [--reps N] [--jobs N]
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
import workflow_ablation as v1  # noqa: E402
import workflow_ablation_v2 as v2  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

from ids2eval.audit import dedup as dedup_mod  # noqa: E402
from ids2eval.audit import homogeneity  # noqa: E402

BASES = ["presplit_hard", "presplit_easy", "group_noisy"]
VARIANTS = [f"{b}_{v}" for b in BASES for v in ("nokey", "randkey")]
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "workflow_ablation_v3.json"


def base_seed(base: str, rep: int) -> int:
    """The generator seed v2 used for this scenario and replicate, so the corpora match Table 3."""
    return 3000 + 100 * v2.SCENARIOS.index(base) + rep


def rekey(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    gid = rng.permutation(len(df)) + 10_000_000
    keyed = v1.tuples(gid)
    for col in keyed.columns:
        df[col] = keyed[col].to_numpy()
    return df


def run_one(variant: str, rep: int) -> dict:
    base, kind = variant.rsplit("_", 1)
    seed = base_seed(base, rep)
    sc = v2.Scenario(base, seed)
    cfg = v1.cfg_for()
    cfg["random_seed"] = seed
    train, test = sc.published
    if kind == "randkey":
        rng = np.random.default_rng(seed + 7)
        train, test = rekey(train, rng), rekey(test, rng)
        if base.startswith("presplit"):
            sc.combined = pd.concat([train, test], ignore_index=True)
        else:
            sc.combined = rekey(sc.combined, rng)
        sc.published = (train, test)
    deploy = sc.deployment()

    gaps = []
    for s in range(v1.N_SEEDS):
        clf = v1.fit(train, v1.FEATS, s)
        gaps.append(v1.acc(clf, test, v1.FEATS) - v1.acc(clf, deploy, v1.FEATS))

    d = dedup_mod.check(train, test, cfg)
    h = homogeneity.check(train, test, cfg)
    classes = [v["classification"] for v in h["details"]["per_class"].values()]
    if kind == "nokey":
        ivs, _ = v2.interventions(sc, cfg, train, test)
        ivs["grouped_resplit"] = {"verdict": "not applicable"}
    else:
        ivs, _ = v2.interventions(sc, cfg, train, test)
    applicable = [v["verdict"] for v in ivs.values() if v["verdict"] != "not applicable"]
    d2 = ("material" if "material" in applicable
          else "not material" if applicable and all(v == "not material" for v in applicable)
          else "inconclusive")
    d4 = ivs["grouped_resplit"]["verdict"]
    d4 = "inconclusive" if d4 == "not applicable" else d4
    d5 = ivs["reuse"]["verdict"] if "reuse" in ivs else "inconclusive"
    gate = d["status"] == "flag" or not (classes and all(c in ("equivalent", "below_control") for c in classes))
    return {"variant": variant, "base": base, "rep": rep, "seed": seed, "truth": v2.TRUTH[base],
            "true_gap": float(np.mean(gaps)), "interventions": ivs, "dedup_status": d["status"],
            "homogeneity_classes": classes, "D2": d2, "D3": d2 if gate else "not material", "D4": d4, "D5": d5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    tasks = [(v, r) for v in VARIANTS for r in range(args.reps)]
    rows = Parallel(n_jobs=args.jobs, verbose=5)(delayed(run_one)(v, r) for v, r in tasks)
    summary = {}
    for variant in VARIANTS:
        rs = [r for r in rows if r["variant"] == variant]
        held = [r for r in rs if r["rep"] not in v2.CAL_SEEDS]
        summary[variant] = {
            "truth": rs[0]["truth"], "gap_mean": float(np.mean([r["true_gap"] for r in rs])),
            "decision_heldout": {k: v2.tally([r[k] for r in held], [r["truth"] for r in held])
                                 for k in ("D2", "D3", "D4", "D5")},
            "decision_all": {k: v2.tally([r[k] for r in rs], [r["truth"] for r in rs])
                             for k in ("D2", "D3", "D4", "D5")},
        }
        print(variant, summary[variant], flush=True)
    Path(args.out).write_text(json.dumps({"threshold": v1.THRESHOLD, "runs": rows, "summary": summary},
                                         indent=2, default=float))
    print("DONE")


if __name__ == "__main__":
    main()
