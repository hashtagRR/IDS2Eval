"""Report exact + feature-space duplicate counts, without mutating the input.

Runs even when preprocessing.dedup is false, so users see how much
duplication is present before deciding whether to remove it.
"""

from __future__ import annotations

import pandas as pd

from .. import dataset


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
    return {"check": "dedup_check", "status": status, "summary": summary, "details": stats}
