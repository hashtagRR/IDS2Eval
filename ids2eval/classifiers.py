"""Registry of the 14 supported classifiers, generalized from the IDS
project's models/classifiers/definitions.py.

Grids here are deliberately smaller than the source project's deep,
dataset-tuned search spaces (e.g. RandomForest's 10-parameter
RandomizedSearchCV grid) — this is a general-purpose default for
arbitrary datasets, not a re-tuned space for one specific dataset's
scale. Override via classifiers.search_space in the config for
anything heavier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import (AdaBoostClassifier, ExtraTreesClassifier,
                               HistGradientBoostingClassifier,
                               RandomForestClassifier, StackingClassifier,
                               VotingClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier


@dataclass
class ClassifierSpec:
    factory: Callable[[dict], Any]     # params -> unfitted estimator
    default_params: dict = field(default_factory=dict)
    default_grid: dict = field(default_factory=dict)
    no_tune: bool = False              # tuning has no effect on this classifier


def _stacking_voting_base(random_state: int = 50):
    return [
        ("rf", RandomForestClassifier(n_estimators=100, random_state=random_state, n_jobs=-1)),
        ("xgb", xgb.XGBClassifier(n_estimators=100, random_state=random_state, n_jobs=-1)),
        ("dt", DecisionTreeClassifier(random_state=random_state)),
    ]


REGISTRY: dict[str, ClassifierSpec] = {
    "RandomForest": ClassifierSpec(
        factory=lambda p: RandomForestClassifier(**p),
        default_params={"n_estimators": 100, "random_state": 50, "n_jobs": -1},
        default_grid={"n_estimators": [100, 200], "max_depth": [10, 20, 30, None],
                      "min_samples_leaf": [1, 2, 4]},
    ),
    "XGBoost": ClassifierSpec(
        factory=lambda p: xgb.XGBClassifier(**p),
        default_params={"n_estimators": 100, "random_state": 50, "n_jobs": -1,
                         "learning_rate": 0.1, "max_depth": 6},
        default_grid={"learning_rate": [0.01, 0.05, 0.1], "max_depth": [6, 10, 15]},
    ),
    "DecisionTree": ClassifierSpec(
        factory=lambda p: DecisionTreeClassifier(**p),
        default_params={"random_state": 50},
        default_grid={"max_depth": [5, 10, 20], "min_samples_split": [2, 5, 10]},
    ),
    "NaiveBayes": ClassifierSpec(
        factory=lambda p: GaussianNB(**p), no_tune=True,
    ),
    "LogisticRegression": ClassifierSpec(
        factory=lambda p: LogisticRegression(**p),
        default_params={"max_iter": 2000, "random_state": 50},
        default_grid={"C": [0.01, 0.1, 1.0, 10.0]},
    ),
    "KNN": ClassifierSpec(
        factory=lambda p: KNeighborsClassifier(**p),
        default_params={"n_neighbors": 5, "n_jobs": -1},
        default_grid={"n_neighbors": [3, 5, 7, 11], "weights": ["uniform", "distance"]},
    ),
    "SVM": ClassifierSpec(
        # LinearSVC scales to large datasets, unlike a full-kernel SVC
        # (O(n^2)-O(n^3)); it has no predict_proba, so it's wrapped in
        # CalibratedClassifierCV to get one.
        factory=lambda p: CalibratedClassifierCV(LinearSVC(**p), cv=5),
        default_params={"max_iter": 2000, "random_state": 50},
        default_grid={"C": [0.1, 1.0, 10.0]},
    ),
    "LDA": ClassifierSpec(
        factory=lambda p: LinearDiscriminantAnalysis(**p),
        default_grid={"solver": ["svd", "lsqr"]},
    ),
    "Stacking": ClassifierSpec(
        factory=lambda p: StackingClassifier(
            estimators=_stacking_voting_base(), final_estimator=LogisticRegression(max_iter=2000), n_jobs=-1,
        ),
        no_tune=True,
    ),
    "Voting": ClassifierSpec(
        factory=lambda p: VotingClassifier(estimators=_stacking_voting_base(), voting="soft", n_jobs=-1),
        no_tune=True,
    ),
    "ExtraTrees": ClassifierSpec(
        factory=lambda p: ExtraTreesClassifier(**p),
        default_params={"n_estimators": 100, "random_state": 50, "n_jobs": -1},
        default_grid={"n_estimators": [100, 200], "max_depth": [10, 20, 30]},
    ),
    "HistGradientBoosting": ClassifierSpec(
        factory=lambda p: HistGradientBoostingClassifier(**p),
        default_params={"max_iter": 100, "random_state": 50},
        default_grid={"max_iter": [50, 100, 200], "learning_rate": [0.01, 0.1, 0.2]},
    ),
    "AdaBoost": ClassifierSpec(
        factory=lambda p: AdaBoostClassifier(**p),
        default_params={"estimator": DecisionTreeClassifier(max_depth=1, random_state=50),
                         "n_estimators": 50, "random_state": 50},
        default_grid={"n_estimators": [50, 100, 200], "learning_rate": [0.5, 1.0, 1.5]},
    ),
    "MLP": ClassifierSpec(
        factory=lambda p: MLPClassifier(**p),
        default_params={"hidden_layer_sizes": (64,), "max_iter": 300,
                         "early_stopping": True, "random_state": 50},
        default_grid={"hidden_layer_sizes": [(64,), (128,), (64, 32)], "alpha": [0.0001, 0.001]},
    ),
}


def build_estimator(name: str, overrides: dict | None = None, seed: int | None = None):
    """Build an unfitted estimator. seed, when given, overrides random_state
    for any classifier that has one in its default_params - but never an
    explicit classifiers.hyperparameters override, which wins on purpose.

    Known simplification: doesn't reach into nested sub-estimators
    (AdaBoost's fixed depth-1 stump, Stacking/Voting's base learners) -
    those keep their own fixed defaults regardless of seed.
    """
    spec = REGISTRY[name]
    overrides = overrides or {}
    params = {**spec.default_params, **overrides}
    if seed is not None and "random_state" in spec.default_params and "random_state" not in overrides:
        params["random_state"] = seed
    return spec.factory(params)
