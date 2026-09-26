"""Temporal-window realism check.

Complements temporal_leakage_check's single aggregate AUC number with a
per-class breakdown: how much of the full capture's time span does
each attack type's own traffic actually cover? A class confined to a
narrow burst window relative to the whole capture (attack X launched
for ten minutes out of a five-day capture) is a specific, checkable
scenario-window artifact. Visible here even when the aggregate
standalone-timestamp AUC isn't dramatically high, because most other
classes are well spread across the full period and only one narrow
class is actually driving the risk.
"""

from __future__ import annotations

import pandas as pd

from . import _by_class
from ._time import to_numeric_time

# Below this share of the full capture's time span, a class's own traffic is
# confined to a narrow enough window that timestamp alone could stand in for
# it, a specific, checkable scenario-window artifact.
BURST_FLAG_THRESHOLD = 0.05
BURST_WARNING_THRESHOLD = 0.15


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    col = cfg["schema"]["timestamp_column"]
    if not col or col not in train_df.columns:
        return {
            "check": "temporal_realism_check", "status": "ok",
            "summary": "no schema.timestamp_column configured", "details": {},
        }

    times = to_numeric_time(train_df[col])
    valid = times.notna()
    if not valid.any():
        return {
            "check": "temporal_realism_check", "status": "ok",
            "summary": "no usable timestamp values to test", "details": {},
        }
    overall_span = times[valid].max() - times[valid].min()
    if not overall_span or overall_span <= 0:
        return {
            "check": "temporal_realism_check", "status": "ok",
            "summary": "timestamp column has no usable time span to test", "details": {},
        }

    group_col = _by_class.group_column(cfg)
    span_by_class = {}
    for cls in _by_class.eligible_classes(train_df, group_col):
        mask = (train_df[group_col] == cls) & valid
        if mask.sum() < _by_class.MIN_CLASS_SIZE:
            continue
        cls_span = times[mask].max() - times[mask].min()
        span_by_class[str(cls)] = float(cls_span / overall_span)

    if not span_by_class:
        return {
            "check": "temporal_realism_check", "status": "ok",
            "summary": "not enough valid timestamps per class to test", "details": {},
        }

    worst_cls, worst_ratio = min(span_by_class.items(), key=lambda kv: kv[1])
    if worst_ratio < BURST_FLAG_THRESHOLD:
        status = "flag"
    elif worst_ratio < BURST_WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "ok"

    summary = f"narrowest class's own time span: '{worst_cls}' covers {worst_ratio:.1%} of the full capture window"
    if status != "ok":
        summary += "; timestamp alone may act as a proxy for this class rather than its actual traffic behavior"

    return {
        "check": "temporal_realism_check", "status": status, "summary": summary,
        "details": {"span_ratio_by_class": span_by_class},
    }
