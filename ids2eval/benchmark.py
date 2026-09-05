"""Classifier benchmarking loop, driven by classifiers.* config.

Runs a "binary" stage against schema.label_column always, and a "type"
stage against schema.attack_category_column if one is configured — two
independent flat benchmarks, not a chained/routed cascade (that
architecture is explicitly out of scope for this tool).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV

from . import classifiers as clf_registry
from . import preprocessing

logger = logging.getLogger(__name__)

MAX_FIT_ROWS = 200_000
TUNING_CV_FOLDS = 3


def run_benchmark(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    schema = cfg["schema"]
    stages = [("binary", schema["label_column"])]
    if schema["attack_category_column"]:
        stages.append(("type", schema["attack_category_column"]))

    x_train_full, x_test, _ = preprocessing.scale_features(train_df, test_df, cfg)

    rows = []
    for stage, label_col in stages:
        y_train_full = train_df[label_col]
        y_test = test_df[label_col]

        if len(x_train_full) > MAX_FIT_ROWS:
            idx = np.random.RandomState(0).choice(len(x_train_full), size=MAX_FIT_ROWS, replace=False)
            x_train, y_train = x_train_full[idx], y_train_full.iloc[idx]
        else:
            x_train, y_train = x_train_full, y_train_full

        x_train_res, y_train_res = preprocessing.apply_sampling(x_train, y_train, cfg, stage)

        for name in _resolve_classifier_list(cfg):
            try:
                model = _fit_classifier(name, x_train_res, y_train_res, cfg)
            except Exception as e:
                logger.warning("Classifier '%s' failed on stage '%s': %s", name, stage, e)
                continue
            rows.append({"stage": stage, "classifier": name, **_evaluate(model, x_test, y_test)})

    return pd.DataFrame(rows)


def _resolve_classifier_list(cfg: dict) -> list[str]:
    clf_list = cfg["classifiers"]["list"]
    return list(clf_registry.REGISTRY) if clf_list == "all" else clf_list


def _fit_classifier(name: str, x_train, y_train, cfg: dict):
    classifiers_cfg = cfg["classifiers"]
    spec = clf_registry.REGISTRY[name]
    overrides = classifiers_cfg["hyperparameters"].get(name, {})

    if classifiers_cfg["tuning"] and not spec.no_tune:
        grid = classifiers_cfg["search_space"].get(name, spec.default_grid)
        if grid:
            base = clf_registry.build_estimator(name, overrides)
            search = GridSearchCV(base, grid, cv=TUNING_CV_FOLDS, n_jobs=-1)
            search.fit(x_train, y_train)
            model = search.best_estimator_
        else:
            model = clf_registry.build_estimator(name, overrides)
            model.fit(x_train, y_train)
    else:
        model = clf_registry.build_estimator(name, overrides)
        model.fit(x_train, y_train)

    calibration = classifiers_cfg["calibration"]
    if calibration != "none" and name != "SVM":  # SVM is already CalibratedClassifierCV-wrapped
        method = "sigmoid" if calibration == "platt" else "isotonic"
        model = CalibratedClassifierCV(model, method=method, cv=5)
        model.fit(x_train, y_train)

    return model


def _evaluate(model, x_test, y_test) -> dict:
    y_pred = model.predict(x_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
    }
    try:
        proba = model.predict_proba(x_test)
        if proba.shape[1] == 2:
            metrics["auc"] = float(roc_auc_score(y_test, proba[:, 1]))
        else:
            metrics["auc"] = float(roc_auc_score(y_test, proba, multi_class="ovr", average="weighted"))
    except (AttributeError, ValueError) as e:
        logger.warning("Could not compute AUC: %s", e)
        metrics["auc"] = None
    return metrics
