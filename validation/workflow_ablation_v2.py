#!/usr/bin/env python3
"""Workflow ablation, second design: evidence quality and decision quality.

The first design (workflow_ablation.py) read a dedup_check flag as a claim
that accuracy is materially inflated, which a duplicate count never claims,
and its W3 verdict came from the interventions alone. This design separates
the two questions a reviewer asked for and adds scenarios built for the full
workflow to fail.

Evidence quality: each stage is scored on the condition it detects.
  dedup_check        does any test row reuse a training feature vector?
  homogeneity_test   do test rows match training more often than training
                     rows match each other, by at least the +0.05 margin?
                     ("leakage" counts as detected; cleared and
                     inconclusive as not detected)
  interventions      is accuracy materially (> 0.01) sensitive to the
                     tested grouping or to the reused rows?

Decision quality: does the published-split accuracy overstate accuracy on
new deployment traffic by more than 0.01? Rules compared:
  D1 dup-share rule      material when the share of reused test rows exceeds
                         a cutoff fitted on generator seeds 0-4 of every
                         scenario (the cutoff maximizing correct answers) and
                         scored on seeds 5-9 only
  D2 intervention only   the verdict of the two interventions, combined as
                         fixed before the first run: material if either is
                         material, not material if every applicable one is
                         not material, otherwise inconclusive (this equals
                         the first design's W3)
  D3 gated               the interventions run only when dedup_check flags
                         or homogeneity_test does not clear every class;
                         otherwise "not material"; reports how many
                         corpora needed the interventions

Scenarios: the six of workflow_ablation.py with the same generator seeds,
plus three where the configured interventions cannot see the cause:
  host_memo     40 hosts with their own feature signature and a random label;
                every row has its own 5-tuple, so the 5-tuple-grouped resplit
                keeps hosts on both sides; deployment brings new hosts
  drift         independent rows; deployment traffic is shifted by one
                standard deviation in two features per class
  prior_shift   independent rows with class priors 0.6/0.25/0.15 in the
                benchmark and 0.2/0.4/0.4 in deployment

Usage: venv/bin/python3 validation/workflow_ablation_v2.py [--reps N] [--jobs N]
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
from joblib import Parallel, delayed  # noqa: E402

from ids2eval.audit import dedup as dedup_mod  # noqa: E402
from ids2eval.audit import homogeneity, repeated_seed_falsification  # noqa: E402
from ids2eval.audit._materiality import accuracy_gap_margin  # noqa: E402
from ids2eval.data import dataset  # noqa: E402

NEW = ["host_memo", "drift", "prior_shift"]
SCENARIOS = v1.SCENARIOS + NEW
TRUTH = {**v1.TRUTH, "host_memo": "material", "drift": "material", "prior_shift": "material"}
REUSE = {"clean": False, "repetitive": True, "group_noisy": False, "group_exact": True,
         "presplit_easy": True, "presplit_hard": True, "host_memo": False, "drift": False,
         "prior_shift": False}
EXCESS = {n: n.startswith("presplit") for n in SCENARIOS}
DEPLOY_PRIORS = [0.2, 0.4, 0.4]
CAL_SEEDS = range(5)  # per-scenario replicate index used to fit D1's cutoff
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "workflow_ablation_v2.json"


class Scenario(v1.Scenario):
    def __init__(self, name: str, seed: int):
        if name in v1.SCENARIOS:
            super().__init__(name, seed)
            return
        rng = np.random.default_rng(seed)
        self.name, self.rng, self.next_gid, self.published = name, rng, 0, None
        if name == "host_memo":
            self.n_hosts = 40
            self.combined = self._hosts(self.n_hosts, v1.N_ROWS)
        else:
            self.draw = v1.shifted(rng, None, 0.9)
            self.combined = self._rows(v1.N_ROWS)
            if name == "drift":
                self.shift = {c: np.zeros(v1.N_FEATS) for c in v1.CLASSES}
                for c in v1.CLASSES:
                    self.shift[c][rng.choice(v1.N_FEATS, 2, replace=False)] = rng.choice([-1.0, 1.0], 2)
        self.published = dataset._random_split(self.combined, "label", {"split_ratio": 0.8}, seed=seed)

    def _hosts(self, n_hosts, n_rows):
        hid = self._gids(n_hosts)
        cent = self.rng.normal(scale=3.0, size=(n_hosts, v1.N_FEATS))
        hlab = self.rng.choice(v1.CLASSES, size=n_hosts, p=v1.PRIORS)
        h = self.rng.integers(0, n_hosts, size=n_rows)
        df = v1.tuples(self._gids(n_rows))  # one 5-tuple per row
        df["src_ip"] = [f"172.16.{x // 250}.{x % 250}" for x in hid[h]]
        df[v1.FEATS] = cent[h] + 0.3 * self.rng.normal(size=(n_rows, v1.N_FEATS))
        df["label"] = hlab[h]
        return df

    def deployment(self):
        if self.name == "host_memo":
            return self._hosts(self.n_hosts, v1.N_DEPLOY)
        if self.name == "drift":
            df = self._rows(v1.N_DEPLOY)
            df[v1.FEATS] = df[v1.FEATS].to_numpy() + np.array([self.shift[c] for c in df["label"]])
            return df
        if self.name == "prior_shift":
            y = self.rng.choice(v1.CLASSES, size=v1.N_DEPLOY, p=DEPLOY_PRIORS)
            df = v1.tuples(self._gids(v1.N_DEPLOY))
            df[v1.FEATS] = self.draw(y)
            df["label"] = y
            return df
        return super().deployment()


def interventions(sc, cfg, train, test):
    rs = repeated_seed_falsification.check(cfg, combined=sc.combined)
    lo, hi = rs["details"]["ci_95"]
    out = {"grouped_resplit": {"mean": rs["details"]["mean_drop"], "ci": [lo, hi], "verdict": v1.verdict(lo, hi)}}
    key = set(pd.util.hash_pandas_object(train[v1.FEATS], index=False))
    novel = test.loc[~pd.util.hash_pandas_object(test[v1.FEATS], index=False).isin(key).to_numpy()]
    if v1.MIN_NOVEL <= len(novel) < len(test):
        drops, a_full, a_nov = [], [], []
        for s in range(v1.N_SEEDS):
            clf = v1.fit(train, v1.FEATS, s)
            a_full.append(v1.acc(clf, test, v1.FEATS))
            a_nov.append(v1.acc(clf, novel, v1.FEATS))
            drops.append(a_full[-1] - a_nov[-1])
        margin = accuracy_gap_margin(np.mean(a_full), len(test), np.mean(a_nov), len(novel))
        m, lo_r, hi_r = v1.t_interval(drops, extra=margin)
        out["reuse"] = {"mean": m, "ci": [lo_r, hi_r], "verdict": v1.verdict(lo_r, hi_r), "novel_rows": int(len(novel))}
    vs = [v["verdict"] for v in out.values()]
    combined = "material" if "material" in vs else ("not material" if all(v == "not material" for v in vs)
                                                     else "inconclusive")
    return out, combined


def run_one(name: str, seed: int, rep: int) -> dict:
    sc = Scenario(name, seed)
    cfg = v1.cfg_for()
    cfg["random_seed"] = seed
    train, test = sc.published
    deploy = sc.deployment()

    gaps = []
    for s in range(v1.N_SEEDS):
        clf = v1.fit(train, v1.FEATS, s)
        gaps.append(v1.acc(clf, test, v1.FEATS) - v1.acc(clf, deploy, v1.FEATS))

    d = dedup_mod.check(train, test, cfg)
    h = homogeneity.check(train, test, cfg)
    classes = [v["classification"] for v in h["details"]["per_class"].values()]
    ivs, d2 = interventions(sc, cfg, train, test)
    gate = d["status"] == "flag" or not (classes and all(c in ("equivalent", "below_control") for c in classes))
    d3 = d2 if gate else "not material"
    return {"scenario": name, "seed": seed, "rep": rep, "truth": TRUTH[name],
            "true_gap": float(np.mean(gaps)),
            "reuse_share": d["details"]["test_leakage_dropped"] / max(len(test), 1),
            "dedup_status": d["status"], "homogeneity_classes": classes, "interventions": ivs,
            "evidence": {"dedup": d["status"] == "flag", "homogeneity": "leakage" in classes,
                         "intervention": d2},
            "D2": d2, "D3": d3, "D3_ran_interventions": bool(gate)}


def fit_cutoff(rows):
    """D1's reuse-share cutoff: the value maximizing correct calls on the calibration replicates."""
    cal = [r for r in rows if r["rep"] in CAL_SEEDS]
    cands = sorted({0.0, *[r["reuse_share"] for r in cal]})
    def score(t):
        return sum((r["reuse_share"] > t) == (r["truth"] == "material") for r in cal)
    return max(cands, key=lambda t: (score(t), -t))


def tally(calls, truth):
    return {"correct": sum(c == t for c, t in zip(calls, truth)),
            "wrong": sum(c not in (t, "inconclusive") for c, t in zip(calls, truth)),
            "inconclusive": sum(c == "inconclusive" for c in calls)}


def summarize(rows):
    cut = fit_cutoff(rows)
    for r in rows:
        r["D1"] = "material" if r["reuse_share"] > cut else "not material"
    table = {"d1_cutoff": cut, "scenarios": {}}
    for name in SCENARIOS:
        rs = [r for r in rows if r["scenario"] == name]
        if not rs:
            continue
        ev = [r for r in rs if r["rep"] not in CAL_SEEDS]  # decision rules scored on held-out replicates
        gaps = [r["true_gap"] for r in rs]
        table["scenarios"][name] = {
            "truth": TRUTH[name], "gap_mean": float(np.mean(gaps)), "gap_sd": float(np.std(gaps, ddof=1)),
            "evidence": {
                "dedup": {"target_present": REUSE[name], "detected": sum(r["evidence"]["dedup"] for r in rs), "n": len(rs)},
                "homogeneity": {"target_present": EXCESS[name], "detected": sum(r["evidence"]["homogeneity"] for r in rs), "n": len(rs)},
                "intervention": tally([r["evidence"]["intervention"] for r in rs], [TRUTH[name]] * len(rs)),
            },
            "decision_heldout": {k: tally([r[k] for r in ev], [r["truth"] for r in ev]) for k in ("D1", "D2", "D3")},
            "decision_all": {k: tally([r[k] for r in rs], [r["truth"] for r in rs]) for k in ("D2", "D3")},
            "D3_interventions_run": sum(r["D3_ran_interventions"] for r in rs),
        }
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    tasks = [(n, 3000 + 100 * i + r, r) for i, n in enumerate(SCENARIOS) if n in args.scenarios
             for r in range(args.reps)]
    rows = Parallel(n_jobs=args.jobs, verbose=5)(delayed(run_one)(n, s, r) for n, s, r in tasks)
    summary = summarize(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"threshold": v1.THRESHOLD, "runs": rows, "summary": summary},
                                         indent=2, default=float))
    print("D1 cutoff", summary["d1_cutoff"])
    for name, e in summary["scenarios"].items():
        print(name, e["truth"], "gap %.3f (%.3f)" % (e["gap_mean"], e["gap_sd"]), "evidence", e["evidence"],
              "held-out", e["decision_heldout"], "D3 ran", e["D3_interventions_run"], flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
