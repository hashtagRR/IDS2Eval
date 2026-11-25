"""How fine a grouping key is.

A grouped split keeps every group on one side of the boundary, so it only
differs from a random split when groups hold several rows. A key that is
nearly unique per row (a 5-tuple with an ephemeral source port, or a key
that includes a timestamp) makes the grouped split almost a random one, and
"no change under grouping" then says little. The grouped checks report these
statistics next to their result so a reader can tell the two cases apart.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def group_stats(df: pd.DataFrame, group_columns: list[str]) -> dict:
    """Group count and size distribution of df under group_columns."""
    sizes = df.groupby(list(group_columns), dropna=False, sort=False).size().to_numpy()
    if len(sizes) == 0:
        return {"group_columns": list(group_columns), "rows": 0, "groups": 0}
    rows = int(sizes.sum())
    singletons = int((sizes == 1).sum())
    q50, q90, q99 = np.percentile(sizes, [50, 90, 99])
    return {
        "group_columns": list(group_columns),
        "rows": rows,
        "groups": len(sizes),
        "rows_per_group": rows / len(sizes),
        "singleton_group_share": singletons / len(sizes),
        "rows_in_singleton_groups": singletons / rows,
        "size_median": float(q50),
        "size_p90": float(q90),
        "size_p99": float(q99),
        "size_max": int(sizes.max()),
        # Share of rows in the largest group: a group that large cannot be balanced
        # across the split, so the split ratio and class mix may drift.
        "largest_group_row_share": float(sizes.max() / rows),
    }


def describe(stats: dict) -> str:
    if not stats.get("groups"):
        return "no groups"
    return (
        f"{stats['groups']:,} groups over {stats['rows']:,} rows "
        f"({stats['rows_per_group']:.2f} rows per group, "
        f"{stats['rows_in_singleton_groups']:.1%} of rows in single-row groups)"
    )
