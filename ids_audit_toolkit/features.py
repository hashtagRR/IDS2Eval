"""Shared feature-matrix prep for audit checks that need to fit a model.

Not a full preprocessing pipeline (no scaling/sampling) — just enough
to turn schema-declared feature columns into a numeric matrix, with
categorical encoding fit on train and applied to test so unseen
categories don't leak information or crash.
"""

from __future__ import annotations

import pandas as pd


def feature_columns(df: pd.DataFrame, cfg: dict) -> list[str]:
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    return [c for c in df.columns if c not in ignore]


def encode_aligned(
    train_df: pd.DataFrame, test_df: pd.DataFrame, columns: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Numeric-encode `columns` in both frames, categories fit on train only.

    Unseen test categories map to -1 rather than raising or silently
    joining an existing code.
    """
    train_out = train_df[columns].copy()
    test_out = test_df[columns].copy()
    for col in columns:
        if train_out[col].dtype == object:
            categories = pd.Index(train_out[col].astype(str).unique())
            train_out[col] = categories.get_indexer(train_out[col].astype(str))
            test_out[col] = categories.get_indexer(test_out[col].astype(str))
        else:
            train_out[col] = pd.to_numeric(train_out[col], errors="coerce").fillna(0)
            test_out[col] = pd.to_numeric(test_out[col], errors="coerce").fillna(0)
    return train_out, test_out
