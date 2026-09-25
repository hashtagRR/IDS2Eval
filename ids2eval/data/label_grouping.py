"""Collapse raw attack-type labels into coarser categories.

Driven by label_grouping.attack_type_mapping: a partial mapping, not an
exhaustive relabeling. {"DoS Hulk": "DoS", "DoS GoldenEye": "DoS"} merges
just those two into "DoS" - any category not named as a mapping key
(e.g. "PortScan") passes through unchanged, so a user can group a
handful of similar attacks into one class without having to enumerate
every other class that should stay as-is.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def apply_attack_type_mapping(
    train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapping = cfg["label_grouping"]["attack_type_mapping"]
    col = cfg["schema"]["attack_category_column"]
    if not mapping:
        return train_df, test_df

    affected = sorted(set(mapping) & set(train_df[col].unique()))
    logger.info(
        "Applying attack_type_mapping to '%s': merging %s into %s",
        col, affected, sorted({mapping[k] for k in affected}),
    )

    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df[col] = train_df[col].replace(mapping)
    test_df[col] = test_df[col].replace(mapping)
    return train_df, test_df
