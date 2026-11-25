"""Shared fit-a-RandomForest-and-score-accuracy helper.

Used by any check that compares accuracy across two different ways of
splitting the same raw data (resplit_falsification: random vs. grouped;
scenario_holdout_falsification: random vs. one scenario held out
entirely), rather than measuring a property of a single given split.
Also used by feature_category_ablation_check, which instead compares
two different FEATURE subsets of the same split, via the optional
`cols` override.

fit_and_evaluate returns the test-set confusion matrix (an
_metrics.Scores), from which the intervention checks read accuracy,
balanced accuracy and macro-F1; fit_and_score returns accuracy alone for
the checks that report only accuracy.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ..data import features
from ._metrics import Scores, scores_from_predictions

MAX_FIT_ROWS = 200_000


def fit_and_evaluate(
    train_df: pd.DataFrame, test_df: pd.DataFrame, label_col: str, cfg: dict,
    cols: list[str] | None = None, seed: int = 0,
) -> Scores:
    """seed controls both which MAX_FIT_ROWS rows are subsampled and the
    RandomForest's own random_state. Callers that want the run's single
    baseline result pass cfg["random_seed"] (the default 0 only applies if a
    caller omits it entirely); repeated_seed_falsification_check is the one
    caller that instead sweeps its own independent range of seeds, to get a
    distribution rather than one baseline point.
    """
    predictions = fit_and_predict(train_df, test_df, label_col, cfg, cols=cols, seed=seed)
    return scores_from_predictions(test_df[label_col].to_numpy(), predictions)


def fit_and_predict(
    train_df: pd.DataFrame, test_df: pd.DataFrame, label_col: str, cfg: dict,
    cols: list[str] | None = None, seed: int = 0,
):
    """The reference model's test-set predictions, for callers that score
    subsets of the test set separately."""
    if cols is None:
        cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols, unseen="missing")
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])
    return clf.predict(x_test)


def fit_and_score(
    train_df: pd.DataFrame, test_df: pd.DataFrame, label_col: str, cfg: dict,
    cols: list[str] | None = None, seed: int = 0,
) -> float:
    """Test-set accuracy of fit_and_evaluate's fit."""
    return fit_and_evaluate(train_df, test_df, label_col, cfg, cols=cols, seed=seed).metrics["accuracy"]
