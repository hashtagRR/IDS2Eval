"""Class-distribution / imbalance report.

Universal IDS-benchmark pattern (KDD99 U2R/R2L <1-2%, BoT-IoT 0.01%
benign, TON_IoT 3.56% benign) — reported unconditionally, not just when
it crosses some threshold, since even a "known" imbalance shifts which
metrics (accuracy vs. F1/AUC) are meaningful for a given dataset.
"""

from __future__ import annotations

import pandas as pd

# A minority class below this share of a split is called out explicitly,
# rather than just left to be read off the full per-class table.
RARE_CLASS_THRESHOLD = 0.01


def _distribution(series: pd.Series) -> dict:
    counts = series.value_counts()
    shares = (counts / counts.sum()).to_dict()
    return {"counts": counts.to_dict(), "shares": shares}


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    label_col = cfg["schema"]["label_column"]
    train_dist = _distribution(train_df[label_col])
    test_dist = _distribution(test_df[label_col])

    train_counts = train_dist["counts"]
    imbalance_ratio = max(train_counts.values()) / max(min(train_counts.values()), 1)
    rare_classes = [c for c, s in train_dist["shares"].items() if s < RARE_CLASS_THRESHOLD]

    status = "warning" if (imbalance_ratio > 100 or rare_classes) else "ok"
    summary = (
        f"{len(train_counts)} classes, train imbalance ratio (majority:minority) "
        f"= {imbalance_ratio:.0f}:1"
    )
    if rare_classes:
        summary += f"; classes below {RARE_CLASS_THRESHOLD:.0%} of train: {rare_classes}"

    return {
        "check": "class_distribution_report",
        "status": status,
        "summary": summary,
        "details": {
            "train": train_dist,
            "test": test_dist,
            "imbalance_ratio": imbalance_ratio,
            "rare_classes": rare_classes,
        },
    }
