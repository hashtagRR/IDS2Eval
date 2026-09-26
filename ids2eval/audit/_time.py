"""Shared timestamp-to-numeric parsing, used by any check scoped to
schema.timestamp_column.
"""

from __future__ import annotations

import pandas as pd


def to_numeric_time(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().mean() > 0.5:
        return parsed.astype("int64") // 10**9
    return pd.to_numeric(series, errors="coerce")
