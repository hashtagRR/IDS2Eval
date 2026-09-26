"""Shared per-class breakdown machinery.

A dataset can look fine in aggregate (8% duplication, say) while one
attack family is 61% duplicated and another is untouched, invisible in
a single global number. The checks that support a breakdown attach a
"by_class" entry to their details, keyed by whichever column groups
attack types: schema.attack_category_column if set, else the label
column itself.

Same MIN_CLASS_SIZE guard homogeneity_test and near_duplicate_class_check
already use: a class with too few rows to say anything meaningful about
is left out rather than reported on a handful of rows.
"""

from __future__ import annotations

import pandas as pd

MIN_CLASS_SIZE = 20


def group_column(cfg: dict) -> str:
    schema = cfg["schema"]
    return schema["attack_category_column"] or schema["label_column"]


def eligible_classes(df: pd.DataFrame, group_col: str, min_size: int = MIN_CLASS_SIZE) -> list:
    counts = df[group_col].value_counts()
    return counts[counts >= min_size].index.tolist()
