#!/usr/bin/env python3
"""Workflow ablation, fourth design: the reuse intervention is reuse_removal_falsification.

workflow_ablation_v2.py and _v3.py scored a "reuse intervention" that compared
accuracy on the whole test set with accuracy on its novel rows. That is an
observational contrast: reused and novel rows can differ in difficulty, so it
does not show what training exposure does. This design replaces it with the
framework's own intervention, reuse_removal_falsification, which removes the
training rows whose feature vector occurs in the test set, refits and scores
the same test set against a class-matched random removal (accuracy verdict,
one-point threshold).

Everything else is unchanged and is read from the stored v2 and v3 results:
the corpora (rebuilt here from the same generator seeds), the deployment gap
and truth, the grouped-resplit verdict, dedup_check and homogeneity_test. To
confirm that the rebuilt corpora are the stored ones, each corpus's reused-row
count is recomputed and must equal the stored dedup_check figure.

The key variants of v3 change only the 5-tuple columns, which the reuse
comparison excludes (schema.drop_columns), so their reuse-removal result is the
base scenario's; the script recomputes it for the first replicate of each
variant to confirm.

Rules, as before: D4 grouped resplit alone, D5 reuse removal alone (an
intervention that cannot run, here because no test row reuses a training
vector, counts as inconclusive), D2 both (material if either applicable one is
material, not material if every applicable one is not material, otherwise
inconclusive), D3 = D2 when dedup_check flags or homogeneity_test does not
clear every class, else not material. D1 is v2's reuse-share rule, unchanged.
Decision rules are scored on held-out replicates 5 to 9.

Rule labels in the output follow v2 and v3. The paper numbers the rules in
reading order: paper D1 = D1 (reuse share), paper D2 = D4 (grouped resplit),
paper D3 = D5 (reuse removal), paper D4 = D2 (both), paper D5 = D3 (gated).

Usage: python3 validation/workflow_ablation_v4.py [--jobs N]
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
import workflow_ablation as v1  # noqa: E402
import workflow_ablation_v2 as v2  # noqa: E402
import workflow_ablation_v3 as v3  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

from ids2eval.audit import reuse_removal  # noqa: E402

ANALYSIS = Path(__file__).resolve().parent.parent / "results" / "analysis"
OUT = ANALYSIS / "workflow_ablation_v4.json"
VERDICT = {"flag": "material", "ok": "not material", "warning": "inconclusive",
           "not_applicable": "not applicable"}


def corpus(scenario: str, seed: int, variant: str | None):
    sc = v2.Scenario(scenario, seed)
    train, test = sc.published
    if variant and variant.endswith("_randkey"):
        rng = np.random.default_rng(seed + 7)
        train, test = v3.rekey(train, rng), v3.rekey(test, rng)
    return train, test


def reuse_verdict(scenario: str, seed: int, variant: str | None = None) -> dict:
    train, test = corpus(scenario, seed, variant)
    cfg = v1.cfg_for()
    cfg["random_seed"] = seed
    r = reuse_removal.check(train, test, cfg)
    acc = r["details"].get("by_metric", {}).get("accuracy", {})
    return {"status": r["status"], "verdict": VERDICT[acc.get("verdict", r["status"])],
            "mean": acc.get("mean_difference"), "ci": acc.get("ci_95"),
            "reused_test_rows": int(np.isin(v1_keys(test), v1_keys(train)).sum()), "test_rows": len(test),
            "training_rows_removed": r["details"].get("training_rows_removed", 0)}


def v1_keys(df):
    import pandas as pd
    return pd.util.hash_pandas_object(df[v1.FEATS], index=False).to_numpy()


def combine(verdicts: list[str]) -> str:
    applicable = [v for v in verdicts if v != "not applicable"]
    if "material" in applicable:
        return "material"
    if applicable and all(v == "not material" for v in applicable):
        return "not material"
    return "inconclusive"


def decide(run: dict, d4: str, d5: str) -> dict:
    d2 = combine([d4, d5])
    classes = run["homogeneity_classes"]
    gate = run["dedup_status"] == "flag" or not (
        classes and all(c in ("equivalent", "below_control") for c in classes))
    return {"D2": d2, "D3": d2 if gate else "not material",
            "D4": "inconclusive" if d4 == "not applicable" else d4,
            "D5": "inconclusive" if d5 == "not applicable" else d5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=-1)
    args = ap.parse_args()
    old2 = json.loads((ANALYSIS / "workflow_ablation_v2.json").read_text())
    old3 = json.loads((ANALYSIS / "workflow_ablation_v3.json").read_text())

    tasks = [(r["scenario"], r["seed"], None) for r in old2["runs"]]
    first_variant = {}
    for r in old3["runs"]:
        if r["rep"] == 0:
            first_variant[r["variant"]] = (r["base"], r["seed"], r["variant"])
    tasks += list(first_variant.values())
    results = Parallel(n_jobs=args.jobs, verbose=5)(delayed(reuse_verdict)(s, seed, var) for s, seed, var in tasks)
    reuse = {(s, seed, var): res for (s, seed, var), res in zip(tasks, results, strict=True)}

    # check 1: the rebuilt corpora are the stored ones
    mismatches = []
    for r in old2["runs"]:
        res = reuse[(r["scenario"], r["seed"], None)]
        if abs(res["reused_test_rows"] / res["test_rows"] - r["reuse_share"]) > 1e-12:
            mismatches.append((r["scenario"], r["seed"], res["reused_test_rows"], res["test_rows"], r["reuse_share"]))
    # check 2: the key variants give the base scenario's reuse result
    variant_mismatch = []
    for var, (base, seed, _) in first_variant.items():
        a, b = reuse[(base, seed, var)], reuse[(base, seed, None)]
        if (a["verdict"], a["mean"]) != (b["verdict"], b["mean"]):
            variant_mismatch.append((var, a, b))

    rows = []
    for r in old2["runs"]:
        d4 = r["interventions"]["grouped_resplit"]["verdict"]
        d5 = reuse[(r["scenario"], r["seed"], None)]["verdict"]
        rows.append({"design": "v2", "scenario": r["scenario"], "rep": r["rep"], "seed": r["seed"],
                     "truth": r["truth"], "true_gap": r["true_gap"], "D1": r.get("D1"),
                     "grouped_resplit": d4, "reuse_removal": reuse[(r["scenario"], r["seed"], None)],
                     **decide(r, d4, d5)})
    for r in old3["runs"]:
        d4 = "not applicable" if r["variant"].endswith("_nokey") else r["interventions"]["grouped_resplit"]["verdict"]
        d5 = reuse[(r["base"], r["seed"], None)]["verdict"]
        rows.append({"design": "v3", "scenario": r["variant"], "rep": r["rep"], "seed": r["seed"],
                     "truth": r["truth"], "true_gap": r["true_gap"], "grouped_resplit": d4,
                     "reuse_removal": reuse[(r["base"], r["seed"], None)], **decide(r, d4, d5)})

    # D1 as stored by v2's summarize (cutoff refit there); recompute it the same way
    for r, o in zip([x for x in rows if x["design"] == "v2"], old2["runs"], strict=True):
        r["reuse_share"] = o["reuse_share"]
    v2_rows = [x for x in rows if x["design"] == "v2"]
    cut = v2.fit_cutoff([{**x, "rep": x["rep"]} for x in v2_rows])
    for x in v2_rows:
        x["D1"] = "material" if x["reuse_share"] > cut else "not material"

    summary = {"d1_cutoff": cut, "corpus_mismatches": mismatches, "variant_mismatches": variant_mismatch,
               "scenarios": {}}
    for name in dict.fromkeys(x["scenario"] for x in rows):
        rs = [x for x in rows if x["scenario"] == name]
        held = [x for x in rs if x["rep"] not in v2.CAL_SEEDS]
        rules = ("D1", "D2", "D3", "D4", "D5") if rs[0]["design"] == "v2" else ("D2", "D3", "D4", "D5")
        summary["scenarios"][name] = {
            "truth": rs[0]["truth"],
            "reuse_removal_all": v2.tally([x["reuse_removal"]["verdict"] if x["reuse_removal"]["verdict"] != "not applicable"
                                           else "inconclusive" for x in rs], [x["truth"] for x in rs]),
            "reuse_removal_not_applicable": sum(x["reuse_removal"]["verdict"] == "not applicable" for x in rs),
            "decision_heldout": {k: v2.tally([x[k] for x in held], [x["truth"] for x in held]) for k in rules},
        }
        print(name, summary["scenarios"][name], flush=True)
    print("corpus mismatches:", mismatches)
    print("variant mismatches:", variant_mismatch)
    OUT.write_text(json.dumps({"threshold": v1.THRESHOLD, "runs": rows, "summary": summary}, indent=2, default=float))
    print("DONE")


if __name__ == "__main__":
    main()
