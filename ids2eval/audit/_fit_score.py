"""Shared fit-a-RandomForest-and-score-accuracy helper.

Used by any check that compares accuracy across two different ways of
splitting the same raw data (resplit_falsification: random vs. grouped;
scenario_holdout_falsification: random vs. one scenario held out
entirely), rather than measuring a property of a single given split.
Also used by feature_category_ablation_check, which instead compares
two different FEATURE subsets of the same split, via the optional
`cols` override.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

from ..data import features

MAX_FIT_ROWS = 200_000


def fit_and_score(
    train_df: pd.DataFrame, test_df: pd.DataFrame, label_col: str, cfg: dict,
    cols: list[str] | None = None, seed: int = 0,
) -> float:
    """seed controls both which MAX_FIT_ROWS rows are subsampled and the
    RandomForest's own random_state. Callers that want the run's single
    baseline result pass cfg["random_seed"] (the default 0 only applies if a
    caller omits it entirely); repeated_seed_falsification_check is the one
    caller that instead sweeps its own independent range of seeds, to get a
    distribution rather than one baseline point.
    """
    if cols is None:
        cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols)
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])
    return float(accuracy_score(test_df[label_col], clf.predict(x_test)))
