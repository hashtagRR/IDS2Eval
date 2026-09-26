"""Label-conflict check: identical features, contradictory labels.

Independently motivated from three directions: Deepchecks' "Conflicting
Labels" check (general ML), Northcutt et al. 2021's finding that label
errors average 3.3% across major ML benchmarks, and Wu & Keogh 2021's
"mislabeled ground truth" flaw in time-series anomaly benchmarks. A feature
vector mapped to more than one label is a stronger, more specific claim
than a duplicate. The ground truth contradicts itself, and no model
can get both instances right regardless of how well it memorizes.

Deliberately scoped like dedup_check: it must run on the RAW data, before
preprocessing.dedup. dataset.dedup() already compares on features only
(ignoring the label column, see dataset.dedup's own docstring), so a
conflicting-label group is exactly the kind of "duplicate" it collapses to
one arbitrarily-kept row - after dedup, every feature vector maps to
exactly one label by construction, and this check will correctly report
zero. That's not the conflict being fixed, just made unobservable; the
"before" pass is what actually shows it existed.

Also attaches a per-class breakdown (details["by_class"]) when flagged:
the global conflict rate can be driven almost entirely by one attack
category, invisible in the aggregate count alone.
"""

from __future__ import annotations

import pandas as pd

from . import _by_class


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    label_col = schema["label_column"]
    group_col = _by_class.group_column(cfg)
    ignore = set(schema["drop_columns"]) | {label_col}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    compare_cols = [c for c in train_df.columns if c not in ignore]
    carry_cols = [label_col] if group_col == label_col else [label_col, group_col]

    combined = pd.concat(
        [
            train_df[[*compare_cols, *carry_cols]].assign(_split="train"),
            test_df[[*compare_cols, *carry_cols]].assign(_split="test"),
        ],
        ignore_index=True,
    )
    # Group on a single hashed key rather than all compare_cols directly: pandas'
    # groupby builds an internal combined index proportional to the number of key
    # columns, which turned out to actually exhaust memory on a real ~2.9M-row,
    # 78-feature run (CIC-IDS2017) - a real OOM kill, not a hypothetical concern.
    # Same hash function dataset.py's own content fingerprint already relies on for
    # an equally big-stakes purpose (proving two runs used identical data), so a
    # collision here is the same astronomically unlikely event, not a new risk.
    combined["_key"] = pd.util.hash_pandas_object(combined[compare_cols], index=False).to_numpy()
    combined["_n_labels"] = combined.groupby("_key", sort=False)[label_col].transform("nunique")
    conflicting = combined[combined["_n_labels"] > 1]

    conflicting_rows = len(conflicting)
    if conflicting_rows == 0:
        return {
            "check": "label_conflict_check", "status": "ok",
            "summary": "no feature vector maps to more than one label", "details": {},
        }

    conflicting_groups = int(conflicting["_key"].nunique())
    cross_split = int((conflicting.groupby("_key", sort=False)["_split"].nunique() > 1).sum())
    pct = conflicting_rows / len(combined)

    summary = (
        f"{conflicting_groups:,} feature vector(s) ({conflicting_rows:,} rows, {pct:.2%}) map to more than "
        f"one label. The ground truth contradicts itself for these rows"
    )
    if cross_split:
        summary += f"; {cross_split:,} of these span train and test"

    conflicting_mask = (combined["_n_labels"] > 1).to_numpy()
    by_class = {}
    for cls in _by_class.eligible_classes(combined, group_col):
        cls_mask = (combined[group_col] == cls).to_numpy()
        by_class[str(cls)] = {"conflicting_rate": float(conflicting_mask[cls_mask].mean())}

    return {
        "check": "label_conflict_check", "status": "flag", "summary": summary,
        "details": {
            "conflicting_groups": conflicting_groups,
            "conflicting_rows": conflicting_rows,
            "cross_split_conflicting_groups": cross_split,
            "by_class": by_class,
        },
    }
