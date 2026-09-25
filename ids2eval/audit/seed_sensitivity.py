"""Seed-sensitivity check (v2, opt-in).

Per D'Amour et al. 2022 (JMLR, "Underspecification Presents Challenges
for Credibility in Modern Machine Learning"): predictors with identical
training-domain performance can behave very differently under stress
tests, purely from iid-performance-preserving perturbations like random
seed choice. leakage_screen and one_rule_check each fit exactly one
seeded classifier and report its result as fact; a borderline result
(say, leakage_screen's top1 share at 0.51 against a 0.5 threshold) could
flip with a different seed and nobody would know. This check re-fits
both across a handful of seeds and reports whether their flag/ok
conclusion is stable, not just their point estimate.

Opt-in rather than v1: it refits two classifiers per seed on top of the
single-seed runs those checks already do, meaningful extra compute on a
large dataset.
"""

from __future__ import annotations

import pandas as pd

from . import leakage, one_rule

SEEDS = (0, 1, 2, 3, 4)


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    leakage_results = [leakage.check(train_df, test_df, cfg, seed=s) for s in SEEDS]
    one_rule_results = [one_rule.check(train_df, test_df, cfg, seed=s) for s in SEEDS]

    leakage_statuses = sorted({r["status"] for r in leakage_results})
    one_rule_statuses = sorted({r["status"] for r in one_rule_results})
    leakage_top1 = [r["details"]["top1_share"] for r in leakage_results if "top1_share" in r["details"]]
    one_rule_acc = [r["details"]["test_accuracy"] for r in one_rule_results if "test_accuracy" in r["details"]]

    unstable = []
    if len(leakage_statuses) > 1:
        unstable.append("leakage_screen")
    if len(one_rule_statuses) > 1:
        unstable.append("one_rule_check")

    parts = []
    if leakage_top1:
        parts.append(
            f"leakage_screen top1 share ranged {min(leakage_top1):.1%}-{max(leakage_top1):.1%} "
            f"across {len(SEEDS)} seeds"
        )
    if one_rule_acc:
        parts.append(
            f"one_rule_check test accuracy ranged {min(one_rule_acc):.1%}-{max(one_rule_acc):.1%} "
            f"across {len(SEEDS)} seeds"
        )
    summary = "; ".join(parts) if parts else "no comparable metric produced by either check across seeds"
    if unstable:
        summary += f". Verdict changed across seeds for: {', '.join(unstable)}"

    return {
        "check": "seed_sensitivity_check",
        "status": "warning" if unstable else "ok",
        "summary": summary,
        "details": {
            "seeds": list(SEEDS),
            "leakage_screen_statuses": leakage_statuses,
            "one_rule_check_statuses": one_rule_statuses,
            "leakage_screen_top1_share_range": [min(leakage_top1), max(leakage_top1)] if leakage_top1 else None,
            "one_rule_check_accuracy_range": [min(one_rule_acc), max(one_rule_acc)] if one_rule_acc else None,
        },
    }
