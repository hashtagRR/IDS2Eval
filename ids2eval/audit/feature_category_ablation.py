"""Feature-category ablation (v2, opt-in).

Needs schema.feature_categories, a user-declared mapping from column
name to a category label (e.g. "behavioural", "topology", "identity",
"timing", any names the user chooses). Fits once on every feature
(baseline), then once per declared category with that category's
columns removed, and reports how much accuracy each category's removal
costs. A category responsible for a large share of the model's
accuracy on its own is worth a second look, especially if it is a
category like identity or topology rather than behavioural, though
this check reports the fact and leaves that judgment to the reader
rather than hardcoding which category names should be considered
suspicious.

Each removal is scored on accuracy, balanced accuracy and macro-F1 (see
_metrics); the status is the most severe verdict among
audit.materiality_metrics, judged on the category whose removal costs that
metric the most.

Deliberately opt-in, not a default check: a category label is exactly
as good as the person who assigned it, unlike every other check here,
which measures something rather than trusting a declared fact. Wrong
labels produce a plausible-looking result that says nothing real.
"""

from __future__ import annotations

import pandas as pd

from ..data import features
from . import _metrics
from ._fit_score import fit_and_evaluate
from ._status import NOT_APPLICABLE

# Overridable via audit.materiality_thresholds.feature_category_ablation_check
# ({"warning": .., "flag": ..}).
MATERIAL_DROP_THRESHOLD = 0.30
WARNING_DROP_THRESHOLD = 0.15


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    categories_map = cfg["schema"]["feature_categories"]
    if not categories_map:
        return {
            "check": "feature_category_ablation_check", "status": NOT_APPLICABLE,
            "summary": "no schema.feature_categories configured", "details": {},
        }

    label_col = cfg["schema"]["label_column"]
    all_cols = features.feature_columns(train_df, cfg)

    by_category: dict[str, list[str]] = {}
    for col, category in categories_map.items():
        if col in all_cols:
            by_category.setdefault(category, []).append(col)
    if not by_category:
        return {
            "check": "feature_category_ablation_check", "status": NOT_APPLICABLE,
            "summary": "none of schema.feature_categories's columns are present in the loaded data",
            "details": {},
        }

    seed = cfg["random_seed"]
    baseline_m = fit_and_evaluate(train_df, test_df, label_col, cfg, cols=all_cols, seed=seed).metrics

    drops_by_category: dict[str, dict[str, float]] = {}
    for category, cols_in_category in by_category.items():
        remaining = [c for c in all_cols if c not in cols_in_category]
        if not remaining:
            continue  # every feature falls under this one category, nothing to ablate against
        ablated_m = fit_and_evaluate(train_df, test_df, label_col, cfg, cols=remaining, seed=seed).metrics
        drops_by_category[category] = {m: baseline_m[m] - ablated_m[m] for m in _metrics.METRICS}

    if not drops_by_category:
        return {
            "check": "feature_category_ablation_check", "status": NOT_APPLICABLE,
            "summary": "every declared category covers all features, nothing left to ablate against",
            "details": {"baseline_accuracy": baseline_m["accuracy"]},
        }

    tiers = _metrics.thresholds(
        cfg, "feature_category_ablation_check",
        {"warning": WARNING_DROP_THRESHOLD, "flag": MATERIAL_DROP_THRESHOLD},
    )
    by_metric, verdicts = {}, {}
    for m in _metrics.METRICS:
        worst = max(drops_by_category, key=lambda c: drops_by_category[c][m])
        verdicts[m] = _metrics.tiered_verdict(drops_by_category[worst][m], tiers[m])
        by_metric[m] = {
            "baseline": baseline_m[m],
            "drop_by_category": {c: d[m] for c, d in drops_by_category.items()},
            "worst_category": worst, "thresholds": tiers[m], "verdict": verdicts[m],
        }
    status = _metrics.combined_status(verdicts, cfg)

    acc = by_metric["accuracy"]
    worst_category, worst_drop = acc["worst_category"], acc["drop_by_category"][acc["worst_category"]]
    summary = (
        f"baseline accuracy={baseline_m['accuracy']:.4f}; removing '{worst_category}' features costs "
        f"{worst_drop:+.4f} accuracy, the most of any declared category; largest balanced accuracy "
        f"drop {by_metric['balanced_accuracy']['drop_by_category'][by_metric['balanced_accuracy']['worst_category']]:+.4f} "
        f"('{by_metric['balanced_accuracy']['worst_category']}') ({_metrics.describe(verdicts)})"
    )
    if status != "ok":
        summary += "; a category this load-bearing is worth checking, especially if it isn't behavioural"

    return {
        "check": "feature_category_ablation_check", "status": status, "summary": summary,
        "details": {
            # Accuracy fields kept under their pre-0.3.0 names for existing readers.
            "baseline_accuracy": baseline_m["accuracy"], "drop_by_category": acc["drop_by_category"],
            "by_metric": by_metric,
            "materiality_metrics": list(cfg["audit"]["materiality_metrics"]),
        },
    }
