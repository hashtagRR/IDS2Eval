"""Scaling and class-balancing, driven by preprocessing.* config.

Sampling is fit on the training split only and never applied to test —
test sets stay at their real-world class distribution so metrics
reflect real deployment, matching the IDS project's balancer.py design.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from imblearn.combine import SMOTEENN
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import EditedNearestNeighbours, RandomUnderSampler
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from . import features

logger = logging.getLogger(__name__)

SCALERS = {"standard": StandardScaler, "minmax": MinMaxScaler, "robust": RobustScaler}
SAMPLERS = {
    "smote": lambda seed: SMOTE(random_state=seed),
    "smoteenn": lambda seed: SMOTEENN(random_state=seed),
    "enn": lambda seed: EditedNearestNeighbours(),  # deterministic, no randomness to seed
    "random_undersample": lambda seed: RandomUnderSampler(random_state=seed),
}


def scale_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    cols = features.feature_columns(train_df, cfg)
    x_train_raw, x_test_raw = features.encode_aligned(train_df, test_df, cols)

    method = cfg["preprocessing"]["scaling"]
    if method == "none":
        return x_train_raw.to_numpy(), x_test_raw.to_numpy(), cols

    scaler = SCALERS[method]()
    x_train = scaler.fit_transform(x_train_raw)
    x_test = scaler.transform(x_test_raw)
    return x_train, x_test, cols


def apply_sampling(x_train: np.ndarray, y_train, cfg: dict, stage: str) -> tuple[np.ndarray, np.ndarray]:
    algo = cfg["preprocessing"]["sampling"][stage]
    if isinstance(algo, list):
        raise ValueError(
            f"preprocessing.sampling.{stage} is a list ({algo}) - apply_sampling takes a "
            "single strategy; use run_benchmark for multi-strategy comparison"
        )
    y_train = np.asarray(y_train)
    if algo == "none":
        return x_train, y_train

    sampler = SAMPLERS[algo](cfg["random_seed"])
    try:
        return sampler.fit_resample(x_train, y_train)
    except ValueError as e:
        logger.warning(
            "Sampling '%s' failed for stage '%s' (%s) — likely a class too small "
            "for this sampler's neighbor count. Falling back to unsampled data.",
            algo, stage, e,
        )
        return x_train, y_train
