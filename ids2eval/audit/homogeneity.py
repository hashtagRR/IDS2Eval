"""Nearest-neighbor class-homogeneity test (paper Section 3.4).

For each class, compares test-to-train nearest-neighbor distance against
a *control* — train-internal nearest-neighbor distance, excluding self.
If test rows are statistically no closer to train than train rows are to
each other, near-duplication is a property of the class population
itself (present within each split independently), not train/test
boundary leakage. If test rows are significantly closer, that's a real
leakage signature the resplit-falsification check can then corroborate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from .. import features

SAMPLE_SIZE = 500
MIN_CLASS_SIZE = 20
MAX_INDEX_ROWS = 200_000
# Post-StandardScaler distance below which two rows are treated as an
# effectively-exact feature-space duplicate.
NEAR_ZERO_DISTANCE = 1e-6


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    group_col = schema["attack_category_column"] or schema["label_column"]
    cols = features.feature_columns(train_df, cfg)

    index_df = train_df.sample(n=min(len(train_df), MAX_INDEX_ROWS), random_state=0)
    x_index_raw, x_test_raw = features.encode_aligned(index_df, test_df, cols)
    scaler = StandardScaler().fit(x_index_raw)
    x_index = scaler.transform(x_index_raw)
    x_test = scaler.transform(x_test_raw)

    nn = NearestNeighbors(n_neighbors=2, algorithm="auto", n_jobs=-1).fit(x_index)

    per_class = {}
    flagged_classes = []
    for cls, count in train_df[group_col].value_counts().items():
        test_mask = test_df[group_col] == cls
        index_mask = (index_df[group_col] == cls).values
        if count < MIN_CLASS_SIZE or test_mask.sum() < MIN_CLASS_SIZE or index_mask.sum() < MIN_CLASS_SIZE:
            continue

        test_sample_idx = np.random.RandomState(0).choice(
            np.flatnonzero(test_mask.values), size=min(SAMPLE_SIZE, test_mask.sum()), replace=False
        )
        control_sample_idx = np.random.RandomState(0).choice(
            np.flatnonzero(index_mask), size=min(SAMPLE_SIZE, index_mask.sum()), replace=False
        )

        test_dist, _ = nn.kneighbors(x_test[test_sample_idx], n_neighbors=1)
        control_dist, _ = nn.kneighbors(x_index[control_sample_idx], n_neighbors=2)

        test_dist = test_dist[:, 0]
        control_dist = control_dist[:, 1]  # nearest neighbor excluding self

        test_near_zero = float((test_dist < NEAR_ZERO_DISTANCE).mean())
        control_near_zero = float((control_dist < NEAR_ZERO_DISTANCE).mean())
        # one-sided: are test rows *significantly closer* to train than
        # train rows are to each other? That direction is the leakage
        # signature; the symmetric case (test farther/equal) is not.
        _, p_value = mannwhitneyu(test_dist, control_dist, alternative="less")

        leakage_signature = p_value < 0.05
        if leakage_signature:
            flagged_classes.append(cls)

        per_class[cls] = {
            "test_near_zero_rate": test_near_zero,
            "control_near_zero_rate": control_near_zero,
            "p_value": float(p_value),
            "leakage_signature": leakage_signature,
        }

    status = "flag" if flagged_classes else "ok"
    summary = (
        f"{len(per_class)} classes tested; "
        + (f"leakage signature (test significantly closer than control, p<0.05) in: {flagged_classes}"
           if flagged_classes else
           "test-to-train and train-internal proximity statistically indistinguishable for every class "
           "(consistent with inherent class homogeneity, not train/test leakage)")
    )
    return {
        "check": "homogeneity_test", "status": status, "summary": summary,
        "details": {"per_class": per_class},
    }
