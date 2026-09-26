"""Report exact + feature-space duplicate counts, without mutating the input.

Runs even when preprocessing.dedup is false, so users see how much
duplication is present before deciding whether to remove it.

Also attaches a per-class breakdown (details["by_class"]): the global
rate can look mild while one attack family carries almost all of it.
Recomputes the same duplicate/leakage masks dataset.dedup() computes
rather than calling it a second time, since dataset.dedup() drops rows
and returns aggregate counts only, not a per-row mask to group by class.
"""

from __future__ import annotations

import pandas as pd

from ..data import dataset
from . import _by_class


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    _, _, stats = dataset.dedup(train_df.copy(), test_df.copy(), cfg)

    total_dropped = (
        stats["train_duplicates_dropped"]
        + stats["test_leakage_dropped"]
        + stats["test_duplicates_dropped"]
    )
    status = "flag" if stats["test_leakage_dropped"] > 0 else (
        "warning" if total_dropped > 0 else "ok"
    )
    summary = (
        f"train duplicates: {stats['train_duplicates_dropped']:,} "
        f"({stats['train_duplicates_dropped'] / max(stats['train_rows_raw'], 1):.2%}); "
        f"test rows leaking a train feature-match: {stats['test_leakage_dropped']:,} "
        f"({stats['test_leakage_dropped'] / max(stats['test_rows_raw'], 1):.2%}); "
        f"test-internal duplicates: {stats['test_duplicates_dropped']:,}"
    )
    details = {**stats, "by_class": _by_class_rates(train_df, test_df, cfg)}
    return {"check": "dedup_check", "status": status, "summary": summary, "details": details}


def _by_class_rates(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    compare_cols = [c for c in train_df.columns if c not in ignore]

    train_dup_mask = train_df.duplicated(subset=compare_cols).to_numpy()
    merged = test_df.merge(
        train_df[compare_cols].drop_duplicates(), on=compare_cols, how="left", indicator=True
    )
    test_leak_mask = (merged["_merge"] == "both").to_numpy()

    group_col = _by_class.group_column(cfg)
    by_class = {}
    for cls in _by_class.eligible_classes(train_df, group_col):
        cls_train_mask = (train_df[group_col] == cls).to_numpy()
        cls_test_mask = (test_df[group_col] == cls).to_numpy()
        by_class[str(cls)] = {
            "train_duplicate_rate": float(train_dup_mask[cls_train_mask].mean()),
            "test_leak_rate": (
                float(test_leak_mask[cls_test_mask].mean()) if cls_test_mask.any() else None
            ),
        }
    return by_class
