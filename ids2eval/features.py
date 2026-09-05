"""Shared feature-matrix prep for audit checks that need to fit a model.

Not a full preprocessing pipeline (no scaling/sampling) — just enough
to turn schema-declared feature columns into a numeric matrix, with
categorical encoding fit on train and applied to test so unseen
categories don't leak information or crash.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Numeric-coerce a column, replacing +-inf as well as NaN with 0.

    Real CIC-IDS2018 quirk hit in practice: rate features like
    'Flow Byts/s' are computed as bytes/duration and are literally
    Infinity when duration is 0 - a valid float, not NaN, so a plain
    .fillna(0) leaves it untouched and it crashes RandomForest ("Input
    X contains infinity"). Zero-filling both is a simple, defensible v1
    choice - a more faithful treatment (matching the IDS project's own
    approach) would cap to the column's observed finite range instead
    of zeroing, preserving "this was an extreme rate" as a signal
    rather than discarding it; not done here for simplicity.
    """
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0)


def feature_columns(df: pd.DataFrame, cfg: dict) -> list[str]:
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    return [c for c in df.columns if c not in ignore]


def encode_multi(
    base_df: pd.DataFrame, other_dfs: list[pd.DataFrame], columns: list[str]
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """Numeric-encode `columns` in base_df and every frame in other_dfs.

    Categories are fit on base_df only and applied identically to every
    other frame, so a cross-dataset comparison (e.g. cross_dataset_drift)
    uses the same encoding on all sides. Unseen categories map to -1
    rather than raising or silently joining an existing code.
    """
    base_out = base_df[columns].copy()
    category_maps: dict[str, pd.Index] = {}
    for col in columns:
        # dtype == object misses pandas' newer dedicated string dtype
        # (pandas >= 2.x with future.infer_string, default in pandas 3.x) —
        # checking is_numeric_dtype instead and treating everything else as
        # categorical is robust to both, and to category dtype too.
        if pd.api.types.is_numeric_dtype(base_out[col]):
            base_out[col] = _coerce_numeric(base_out[col])
        else:
            categories = pd.Index(base_out[col].astype(str).unique())
            category_maps[col] = categories
            base_out[col] = categories.get_indexer(base_out[col].astype(str))

    others_out = []
    for other_df in other_dfs:
        other_out = other_df[columns].copy()
        for col in columns:
            if col in category_maps:
                other_out[col] = category_maps[col].get_indexer(other_out[col].astype(str))
            else:
                other_out[col] = _coerce_numeric(other_out[col])
        others_out.append(other_out)
    return base_out, others_out


def encode_aligned(
    train_df: pd.DataFrame, test_df: pd.DataFrame, columns: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Numeric-encode `columns` in both frames, categories fit on train only.

    Unseen test categories map to -1 rather than raising or silently
    joining an existing code.
    """
    train_out, (test_out,) = encode_multi(train_df, [test_df], columns)
    return train_out, test_out
