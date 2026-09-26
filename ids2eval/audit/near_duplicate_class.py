"""Near-duplicate feature vectors across different classes.

label_conflict_check catches identical features mapped to different
labels. This extends that to features close enough in scaled distance
to be effectively identical without matching exactly, the common case
when the same traffic-generation script produced two nominally
different attack labels, or two attack tools share almost all of their
flow statistics. Runs on train only: this is about label confusability
within the data a model actually learns from, not a train/test split
property (that's homogeneity_test's job).

Same nearest-neighbor machinery and near-zero distance threshold as
homogeneity_test, applied across classes rather than across the split.
A single NearestNeighbors index over all sampled rows, queried once,
avoids an O(classes^2) pairwise comparison.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from ..data import features

SAMPLE_SIZE = 500
MIN_CLASS_SIZE = 20
NEAR_ZERO_DISTANCE = 1e-6


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    group_col = schema["attack_category_column"] or schema["label_column"]
    cols = features.feature_columns(train_df, cfg)

    class_counts = train_df[group_col].value_counts()
    eligible = class_counts[class_counts >= MIN_CLASS_SIZE].index
    if len(eligible) < 2:
        return {
            "check": "near_duplicate_class_check", "status": "ok",
            "summary": "fewer than two classes have enough rows to compare", "details": {},
        }

    rng = np.random.RandomState(0)
    sample_parts = []
    for cls in eligible:
        idx = np.flatnonzero((train_df[group_col] == cls).to_numpy())
        chosen = rng.choice(idx, size=min(SAMPLE_SIZE, len(idx)), replace=False)
        sample_parts.append(train_df.iloc[chosen])
    sample_df = pd.concat(sample_parts, ignore_index=True)

    x_raw = features.encode_aligned(sample_df, sample_df, cols)[0]
    x = StandardScaler().fit_transform(x_raw)
    labels = sample_df[group_col].to_numpy()

    nn = NearestNeighbors(n_neighbors=2, algorithm="auto", n_jobs=-1).fit(x)
    dist, idx = nn.kneighbors(x)
    nearest_dist, nearest_idx = dist[:, 1], idx[:, 1]  # excluding self

    cross_label = labels != labels[nearest_idx]
    near_zero = nearest_dist < NEAR_ZERO_DISTANCE
    confused = cross_label & near_zero

    if not confused.any():
        return {
            "check": "near_duplicate_class_check", "status": "ok",
            "summary": f"no near-zero-distance feature vectors found across {len(eligible)} classes tested",
            "details": {"classes_tested": len(eligible)},
        }

    pairs = pd.Series(
        [tuple(sorted((a, b))) for a, b in zip(labels[confused], labels[nearest_idx[confused]], strict=True)]
    ).value_counts()
    top_pairs = {f"{a} / {b}": int(n) for (a, b), n in pairs.head(5).items()}
    affected_rows = int(confused.sum())
    pct = affected_rows / len(sample_df)

    summary = (
        f"{affected_rows:,} of {len(sample_df):,} sampled rows ({pct:.2%}) have a near-zero-distance "
        f"neighbor under a different label. Most affected pairs: {top_pairs}"
    )
    return {
        "check": "near_duplicate_class_check", "status": "flag", "summary": summary,
        "details": {"classes_tested": len(eligible), "affected_rows": affected_rows, "top_pairs": top_pairs},
    }
