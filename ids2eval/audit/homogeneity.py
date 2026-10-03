"""Nearest-neighbor class-homogeneity test (paper Section 3.4).

For each class, compares test-to-train nearest-neighbor distance against
a *control*, train-internal nearest-neighbor distance, excluding self, via
the near-zero-distance rate each side shows (the share of rows whose
nearest neighbor is an effectively-exact feature-space duplicate). If test
rows are no more prone to this than train rows are to each other,
near-duplication is a property of the class population itself (present
within each split independently), not train/test boundary leakage. If
test rows are notably more prone to it, that's a real leakage signature
the resplit-falsification check can then corroborate.

Reports this as a genuine equivalence test, not an unreplicated
non-significance claim: failing to detect a difference is not the same
claim as having shown the two rates are close, so this computes a 95%
CI on the rate difference (test minus control) and classifies each class
against a pre-specified equivalence margin, the same three-way
material/not-material/inconclusive pattern already used by
repeated_seed_falsification_check for the same reason - "statistically
indistinguishable" from a single p-value conflates "no detected
difference" with "shown to be equivalent," two different claims.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from . import _materiality
from ..data import features

SAMPLE_SIZE = 500
MIN_CLASS_SIZE = 20
MAX_INDEX_ROWS = 200_000
# Post-StandardScaler distance below which two rows are treated as an
# effectively-exact feature-space duplicate.
NEAR_ZERO_DISTANCE = 1e-6
# Equivalence margin on the near-zero-distance *rate difference* (test minus
# control), on the same 0-1 scale as the rates themselves: if test rows are
# near-zero-distance to train no more than 5 percentage points more often
# than train rows are to each other, that gap is read as noise around zero,
# not a leakage signature - the same order of magnitude as this codebase's
# other diagnostic materiality thresholds (e.g. resplit_falsification's 0.01
# accuracy-drop, result_robustness_check's 0.08/0.15 spread tiers), chosen
# for consistency rather than independently derived. Overridable via
# audit.materiality_thresholds.homogeneity_test.
EQUIVALENCE_MARGIN = 0.05


def _rate_diff_ci(p_test: float, n_test: int, p_control: float, n_control: int) -> tuple[float, float]:
    """95% Wald CI for the difference of two independent proportions
    (test rate minus control rate). Adequate at this check's sample sizes
    (up to SAMPLE_SIZE=500 per side); not Wilson/Newcombe-corrected, since
    this is a diagnostic threshold comparison, not a primary estimate."""
    diff = p_test - p_control
    se = math.sqrt(
        p_test * (1 - p_test) / n_test + p_control * (1 - p_control) / n_control
    )
    margin = 1.959964 * se  # z_{0.975}
    return diff - margin, diff + margin


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    group_col = schema["attack_category_column"] or schema["label_column"]
    cols = features.feature_columns(train_df, cfg)

    index_df = train_df.sample(n=min(len(train_df), MAX_INDEX_ROWS), random_state=cfg["random_seed"])
    x_index_raw, x_test_raw = features.encode_aligned(index_df, test_df, cols)
    scaler = StandardScaler().fit(x_index_raw)
    x_index = scaler.transform(x_index_raw)
    x_test = scaler.transform(x_test_raw)

    nn = NearestNeighbors(n_neighbors=2, algorithm="auto", n_jobs=-1).fit(x_index)
    margin = _materiality.threshold(cfg, "homogeneity_test", EQUIVALENCE_MARGIN)

    per_class = {}
    flagged_classes = []
    inconclusive_classes = []
    for cls, count in train_df[group_col].value_counts().items():
        test_mask = test_df[group_col] == cls
        index_mask = (index_df[group_col] == cls).values
        if count < MIN_CLASS_SIZE or test_mask.sum() < MIN_CLASS_SIZE or index_mask.sum() < MIN_CLASS_SIZE:
            continue

        test_sample_idx = np.random.RandomState(0).choice(
            np.flatnonzero(test_mask.values), size=min(SAMPLE_SIZE, test_mask.sum()), replace=False
        )
        control_sample_idx = np.random.RandomState(0).choice(
            np.flatnonzero(index_mask), size=min(SAMPLE_SIZE, index_mask.sum()), replace=False
        )

        test_dist, _ = nn.kneighbors(x_test[test_sample_idx], n_neighbors=1)
        control_dist, _ = nn.kneighbors(x_index[control_sample_idx], n_neighbors=2)

        test_dist = test_dist[:, 0]
        control_dist = control_dist[:, 1]  # nearest neighbor excluding self

        test_near_zero = float((test_dist < NEAR_ZERO_DISTANCE).mean())
        control_near_zero = float((control_dist < NEAR_ZERO_DISTANCE).mean())
        n_test, n_control = len(test_dist), len(control_dist)
        ci_low, ci_high = _rate_diff_ci(test_near_zero, n_test, control_near_zero, n_control)

        # Three-way, same pattern as repeated_seed_falsification_check: the CI's
        # lower bound above the margin is a real leakage signature even at the
        # most conservative estimate; the CI entirely within +/-margin is a
        # genuine equivalence claim, not just "no difference detected"; anything
        # straddling either boundary is inconclusive, not silently "ok".
        if ci_low > margin:
            classification = "leakage"
            flagged_classes.append(cls)
        elif ci_low > -margin and ci_high < margin:
            classification = "equivalent"
        else:
            classification = "inconclusive"
            inconclusive_classes.append(cls)

        per_class[cls] = {
            "test_near_zero_rate": test_near_zero,
            "control_near_zero_rate": control_near_zero,
            "rate_diff_ci_95": [ci_low, ci_high],
            "equivalence_margin": margin,
            "classification": classification,
        }

    status = "flag" if flagged_classes else ("warning" if inconclusive_classes else "ok")
    if flagged_classes:
        detail = f"leakage signature (95% CI lower bound exceeds the {margin:+.2f} margin) in: {flagged_classes}"
    elif inconclusive_classes:
        detail = (
            f"inconclusive (95% CI straddles the +/-{margin:.2f} equivalence margin) for: "
            f"{inconclusive_classes}; sample size isn't enough to tell for these classes"
        )
    else:
        detail = (
            f"test-to-train and train-internal near-duplicate rates fall within a pre-specified "
            f"+/-{margin:.2f} equivalence margin for every class (95% CI), consistent with inherent "
            f"class homogeneity rather than train/test leakage"
        )
    summary = f"{len(per_class)} classes tested; {detail}"

    return {
        "check": "homogeneity_test", "status": status, "summary": summary,
        "details": {"per_class": per_class, "equivalence_margin": margin},
    }
