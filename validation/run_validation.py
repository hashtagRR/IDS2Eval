#!/usr/bin/env python3
"""Runs the synthetic validation corpus (fixtures.py) against IDS2Eval's own
check functions and reports whether each check correctly fires on its
matched positive (defect present) fixture and stays clean on its matched
negative (defect absent) fixture.

Usage: venv/bin/python3 validation/run_validation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixtures import FIXTURES, IMBALANCE_EXPECTED_CLEAN, IMBALANCE_EXPECTED_FIRES, imbalance_control

from ids2eval.audit import (
    class_distribution,
    dedup,
    feature_auc_ranking,
    homogeneity,
    identity_columns,
    label_conflict,
    near_duplicate_class,
    one_rule,
    port_protocol_shortcut,
    repeated_seed_falsification,
    resplit,
    result_robustness,
    row_order_leakage,
    temporal_leakage,
    temporal_realism,
)

CHECK_FUNCS = {
    "dedup_check": lambda train, test, cfg: dedup.check(train, test, cfg),
    "label_conflict_check": lambda train, test, cfg: label_conflict.check(train, test, cfg),
    "near_duplicate_class_check": lambda train, test, cfg: near_duplicate_class.check(train, cfg),
    "identity_column_flag": lambda train, test, cfg: identity_columns.check_predictive_power(train, test, cfg),
    "low_cardinality_warning": lambda train, test, cfg: identity_columns.check_cardinality(train, cfg),
    "port_protocol_shortcut_check": lambda train, test, cfg: port_protocol_shortcut.check(train, test, cfg),
    "one_rule_check": lambda train, test, cfg: one_rule.check(train, test, cfg, seed=cfg["random_seed"]),
    "row_order_leakage_check": lambda train, test, cfg: row_order_leakage.check(train, test, cfg),
    "temporal_leakage_check": lambda train, test, cfg: temporal_leakage.check(train, test, cfg),
    "temporal_realism_check": lambda train, test, cfg: temporal_realism.check(train, cfg),
    "homogeneity_test": lambda train, test, cfg: homogeneity.check(train, test, cfg),
    # these three build their own splits from the combined data passed as `train`
    "resplit_falsification": lambda train, test, cfg: resplit.check(cfg, seed=cfg["random_seed"], combined=train),
    "repeated_seed_falsification_check": lambda train, test, cfg: repeated_seed_falsification.check(
        cfg, combined=train),
    "result_robustness_check": lambda train, test, cfg: result_robustness.check(cfg, combined=train),
    "class_distribution_report": lambda train, test, cfg: class_distribution.check(train, test, cfg),
    "feature_auc_ranking_check": lambda train, test, cfg: feature_auc_ranking.check(train, cfg),
}

# A check "fires" if its status is anything other than ok.
EXPECTED = {"positive": "fires", "negative": "clean"}


def status_bucket(status: str) -> str:
    return "clean" if status == "ok" else "fires"


def main() -> int:
    results = []
    all_pass = True
    for check_name, spec in FIXTURES.items():
        for polarity in ("positive", "negative"):
            train, test, cfg = spec[polarity]()
            finding = CHECK_FUNCS[check_name](train, test, cfg)
            actual_status = finding["status"]
            actual_bucket = status_bucket(actual_status)
            expected_bucket = EXPECTED[polarity]
            passed = actual_bucket == expected_bucket
            all_pass = all_pass and passed
            results.append({
                "check": check_name,
                "defect": spec["defect"],
                "polarity": polarity,
                "expected": expected_bucket,
                "actual_status": actual_status,
                "actual_bucket": actual_bucket,
                "passed": passed,
                "summary": finding["summary"],
            })

    print(f"{'Check':<30} {'Polarity':<10} {'Expected':<10} {'Actual':<10} {'Result':<6}  Summary")
    print("-" * 140)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(
            f"{r['check']:<30} {r['polarity']:<10} {r['expected']:<10} {r['actual_bucket']:<10} "
            f"{mark:<6}  {r['summary'][:70]}"
        )

    train, test, cfg = imbalance_control()
    for check_name in IMBALANCE_EXPECTED_FIRES + IMBALANCE_EXPECTED_CLEAN:
        finding = CHECK_FUNCS[check_name](train, test, cfg)
        expected_bucket = "fires" if check_name in IMBALANCE_EXPECTED_FIRES else "clean"
        actual_bucket = status_bucket(finding["status"])
        passed = actual_bucket == expected_bucket
        all_pass = all_pass and passed
        results.append({
            "check": check_name, "defect": "negative control: 0.5% minority class, no leakage",
            "polarity": "imbalance", "expected": expected_bucket, "actual_status": finding["status"],
            "actual_bucket": actual_bucket, "passed": passed, "summary": finding["summary"],
        })
        mark = "PASS" if passed else "FAIL"
        print(f"{check_name:<30} {'imbalance':<10} {expected_bucket:<10} {actual_bucket:<10} {mark:<6}  "
              f"{finding['summary'][:70]}")

    n_pass = sum(1 for r in results if r["passed"])
    print()
    print(f"{n_pass}/{len(results)} fixture evaluations passed ({len(FIXTURES)} defects x 2 polarities, "
          f"plus {len(IMBALANCE_EXPECTED_FIRES) + len(IMBALANCE_EXPECTED_CLEAN)} checks on the imbalance control)")

    out_path = Path(__file__).resolve().parent.parent / "results" / "analysis" / "validation_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Full results written to {out_path}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
