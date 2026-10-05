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

Reports a 95% CI on the rate difference (test minus control) against a
pre-specified margin rather than a single p-value, since failing to detect
a difference is not the same claim as having shown there is none. Leakage
is one-sided, so a class is "leakage" when the CI's lower bound exceeds
+margin, cleared when its upper bound is below +margin ("equivalent" if
the CI also sits inside +/-margin, "below_control" if test rows are
materially less near-duplicated than train is with itself), and
"inconclusive" when the CI straddles +margin.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from ..data import features
from . import _materiality

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


_Z = 1.959964  # z_{0.975}


def _wilson(p: float, n: int) -> tuple[float, float]:
    centre = (p + _Z**2 / (2 * n)) / (1 + _Z**2 / n)
    half = _Z * math.sqrt(p * (1 - p) / n + _Z**2 / (4 * n**2)) / (1 + _Z**2 / n)
    return centre - half, centre + half


def _rate_diff_ci(p_test: float, n_test: int, p_control: float, n_control: int) -> tuple[float, float]:
    """95% Newcombe hybrid-score CI for the difference of two independent
    proportions (test rate minus control rate). Unlike the Wald interval it
    stays a proper interval when a rate is at 0 or 1, which match rates
    often are here."""
    diff = p_test - p_control
    lo_t, hi_t = _wilson(p_test, n_test)
    lo_c, hi_c = _wilson(p_control, n_control)
    lower = diff - math.sqrt((p_test - lo_t) ** 2 + (hi_c - p_control) ** 2)
    upper = diff + math.sqrt((hi_t - p_test) ** 2 + (p_control - lo_c) ** 2)
    return lower, upper


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

        # Leakage is one-sided (test closer to train than the control), so the
        # decision bound is +margin only. A CI entirely below -margin means the
        # test rows are materially *less* near-duplicated than train is with
        # itself: decisively not leakage, so it must not land in "inconclusive".
        if ci_low > margin:
            classification = "leakage"
            flagged_classes.append(cls)
        elif ci_high < margin:
            classification = "equivalent" if ci_low > -margin else "below_control"
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
            f"for every class the 95% CI upper bound on (test-to-train minus train-internal) "
            f"near-duplicate rate is below the +{margin:.2f} margin, so no class shows a "
            f"train/test leakage signature"
        )
    summary = f"{len(per_class)} classes tested; {detail}"

    return {
        "check": "homogeneity_test", "status": status, "summary": summary,
        "details": {"per_class": per_class, "equivalence_margin": margin},
    }
