"""Row-order (sequence) leakage check.

Datasets assembled by concatenating scenario-specific collection blocks
(benign traffic captured first, then one attack type, then the next)
leave a detectable signature in raw row order: adjacent rows share a
label far more often than a randomly shuffled arrangement of the same
label distribution would. Measured via the number of label transitions
between adjacent rows (a Wald-Wolfowitz runs statistic), compared
against the closed-form expectation for a shuffled multiset (the
Simpson-diversity complement, 1 - sum(p_i^2), the exact probability two
independently drawn labels differ), rather than fitting and evaluating
a model.

A standalone-AUC check, the method identity_column_flag and
temporal_leakage_check use, does not fit this signal: that method needs
the same feature to be directly comparable between train and test (a
shared timestamp, a shared IP space). Row position within one dataframe
has no such correspondence to row position within another, so train
and test are each tested against their own row order independently,
not fit on one and evaluated on the other.
"""

from __future__ import annotations

import pandas as pd

# Below this share of the shuffled-baseline transition rate, adjacent rows
# share a label often enough to be a specific, checkable block-ordering
# signature, not incidental clustering.
CONTIGUITY_FLAG_THRESHOLD = 0.3
CONTIGUITY_WARNING_THRESHOLD = 0.6


def _contiguity_ratio(labels: pd.Series) -> float | None:
    n = len(labels)
    if n < 2:
        return None
    values = labels.to_numpy()
    observed_transitions = int((values[1:] != values[:-1]).sum())
    shares = labels.value_counts(normalize=True).to_numpy()
    expected_rate = 1.0 - float((shares**2).sum())
    if expected_rate <= 0:
        return None  # a single class: no transition rate to compare against
    observed_rate = observed_transitions / (n - 1)
    return observed_rate / expected_rate


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    label_col = cfg["schema"]["label_column"]
    ratios = {
        "train": _contiguity_ratio(train_df[label_col]),
        "test": _contiguity_ratio(test_df[label_col]),
    }
    valid = {split: ratio for split, ratio in ratios.items() if ratio is not None}
    if not valid:
        return {
            "check": "row_order_leakage_check", "status": "ok",
            "summary": "not enough rows or classes in either split to test row order",
            "details": {},
        }

    worst_split, worst_ratio = min(valid.items(), key=lambda kv: kv[1])
    if worst_ratio < CONTIGUITY_FLAG_THRESHOLD:
        status = "flag"
    elif worst_ratio < CONTIGUITY_WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "ok"

    ratio_text = ", ".join(f"{split}={ratio:.2f}" for split, ratio in valid.items())
    summary = (
        f"adjacent-row label-transition rate ({ratio_text}) as a share of what a "
        f"randomly shuffled ordering would produce"
    )
    if status != "ok":
        summary += (
            f"; {worst_split} is the most contiguous, consistent with rows still in "
            f"collection order rather than shuffled before this split"
        )

    return {
        "check": "row_order_leakage_check", "status": status, "summary": summary,
        "details": {"contiguity_ratio": ratios},
    }
