"""Load raw or pre-split IDS data and produce a train/test split.

Ported and generalized from the IDS project's data/loader.py and
data/preprocessor.py._deduplicate — same session-grouped-split and
feature-space-dedup logic, but driven by config instead of hardcoded
per-dataset column names.
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

logger = logging.getLogger(__name__)


def load_raw_combined(dataset_cfg: dict) -> pd.DataFrame:
    """Load and concatenate dataset.raw_files, before any split is applied."""
    frames = [pd.read_csv(path) for path in dataset_cfg["raw_files"]]
    for df in frames:
        df.columns = df.columns.str.strip()
    return pd.concat(frames, ignore_index=True, copy=False)


def load_split(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train_df, test_df), pre-split if configured, else loaded+split."""
    dataset_cfg = cfg["dataset"]
    if dataset_cfg["train_file"] and dataset_cfg["test_file"]:
        train_df = pd.read_csv(dataset_cfg["train_file"])
        test_df = pd.read_csv(dataset_cfg["test_file"])
        return train_df, test_df

    combined = load_raw_combined(dataset_cfg)
    label_col = cfg["schema"]["label_column"]
    if dataset_cfg["split_mode"] == "grouped":
        return _grouped_split(combined, label_col, dataset_cfg)
    return _random_split(combined, label_col, dataset_cfg)


def _random_split(
    df: pd.DataFrame, label_col: str, dataset_cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train, test = train_test_split(
        df,
        test_size=1.0 - dataset_cfg["split_ratio"],
        random_state=0,
        stratify=df[label_col],
    )
    return train.reset_index(drop=True), test.reset_index(drop=True)


def _grouped_split(
    df: pd.DataFrame, label_col: str, dataset_cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Session/time-grouped split via StratifiedGroupKFold.

    Keeps every group_columns combination on one side of the split, so
    session-correlated leakage across the train/test boundary is
    structurally impossible — see the resplit-falsification audit check,
    which uses this same split as its counterfactual.
    """
    group_cols = [c for c in dataset_cfg["group_columns"] if c in df.columns]
    if not group_cols:
        raise ValueError(
            f"None of dataset.group_columns {dataset_cfg['group_columns']} "
            f"are present in the loaded data"
        )
    groups = df[group_cols].astype(str).agg("|".join, axis=1)

    n_splits = round(1.0 / (1.0 - dataset_cfg["split_ratio"]))
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=0)
    train_idx, test_idx = next(sgkf.split(df, df[label_col], groups))
    train = df.iloc[train_idx].reset_index(drop=True)
    test = df.iloc[test_idx].reset_index(drop=True)

    train_groups = set(groups.iloc[train_idx])
    test_groups = set(groups.iloc[test_idx])
    overlap = train_groups & test_groups
    if overlap:
        raise RuntimeError(
            f"Grouped split produced {len(overlap)} groups on both sides of "
            "train/test — StratifiedGroupKFold invariant violated, refusing "
            "to silently continue."
        )
    logger.info(
        "Grouped split: %d groups total, %d train / %d test, zero overlap confirmed.",
        len(train_groups | test_groups), len(train_groups), len(test_groups),
    )
    return train, test


def dedup(
    train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Drop exact feature-space duplicates within and across splits.

    Compares on every column except schema.drop_columns/label_column/
    attack_category_column — a test row whose FEATURES exactly duplicate
    a train row measures memorization, not generalization, regardless of
    whether its label happens to match.
    """
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    compare_cols = [c for c in train_df.columns if c not in ignore]

    n_train0, n_test0 = len(train_df), len(test_df)

    n_train_dupe = int(train_df.duplicated(subset=compare_cols).sum())
    train_df = train_df.drop_duplicates(subset=compare_cols).reset_index(drop=True)

    merged = test_df.merge(
        train_df[compare_cols].drop_duplicates(), on=compare_cols, how="left", indicator=True
    )
    leak_mask = (merged["_merge"] == "both").values
    n_leak = int(leak_mask.sum())
    test_df = test_df.loc[~leak_mask].reset_index(drop=True)

    n_test_dupe = int(test_df.duplicated(subset=compare_cols).sum())
    test_df = test_df.drop_duplicates(subset=compare_cols).reset_index(drop=True)

    stats = {
        "train_rows_raw": n_train0,
        "train_rows_deduped": len(train_df),
        "train_duplicates_dropped": n_train_dupe,
        "test_rows_raw": n_test0,
        "test_rows_deduped": len(test_df),
        "test_leakage_dropped": n_leak,
        "test_duplicates_dropped": n_test_dupe,
    }
    return train_df, test_df, stats
