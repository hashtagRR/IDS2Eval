#!/usr/bin/env python3
"""reuse_removal_falsification on the official UNSW-NB15 and NSL-KDD partitions,
with three models.

The check removes every training row whose feature vector occurs in the test
set, refits, and scores the same test set against a same-size random removal
with the same class mix. It is run here as released, once per model, by
replacing only the function that fits the model and predicts:

  rf    the reference random forest (100 trees, at most 200,000 training rows),
        audit.repeated_seed_count = 10
  knn1  1-nearest-neighbour on standardized features: it memorizes every
        training row, so it should profit most from seeing a test vector;
        5 seeds
  xgb   gradient-boosted trees (XGBoost, 100 trees, depth 8, the settings of
        the paper's other model families); 5 seeds

Run from the directory that holds data/ (the files the configs name).

Usage: python3 validation/reuse_removal_models.py OUT_JSON [DATASET ...]
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ids2eval.audit import _fit_score, reuse_removal
from ids2eval.config import load_config
from ids2eval.data import dataset, features

CONFIGS = Path(__file__).resolve().parent.parent / "results" / "configs"
DATASETS = ["unsw-nb15", "nsl-kdd"]
SEEDS = {"rf": 10, "knn1": 5, "xgb": 5}


def _encoded(train_df, test_df, label_col, cfg):
    cols = features.feature_columns(train_df, cfg)
    x_train, x_test = features.encode_aligned(train_df, test_df, cols, unseen="missing")
    return x_train.to_numpy(dtype=float), x_test.to_numpy(dtype=float)


def knn1_predict(train_df, test_df, label_col, cfg, cols=None, seed=0):
    x_train, x_test = _encoded(train_df, test_df, label_col, cfg)
    x_train, x_test = np.nan_to_num(x_train, nan=-1.0), np.nan_to_num(x_test, nan=-1.0)
    scaler = StandardScaler().fit(x_train)
    model = KNeighborsClassifier(n_neighbors=1, n_jobs=-1).fit(scaler.transform(x_train), train_df[label_col])
    return model.predict(scaler.transform(x_test))


def xgb_predict(train_df, test_df, label_col, cfg, cols=None, seed=0):
    x_train, x_test = _encoded(train_df, test_df, label_col, cfg)
    encoder = LabelEncoder().fit(train_df[label_col])
    model = XGBClassifier(n_estimators=100, max_depth=8, random_state=seed, n_jobs=-1, tree_method="hist")
    model.fit(x_train, encoder.transform(train_df[label_col]))
    return encoder.inverse_transform(model.predict(x_test))


PREDICTORS = {"rf": _fit_score.fit_and_predict, "knn1": knn1_predict, "xgb": xgb_predict}


def main() -> None:
    out = Path(sys.argv[1])
    names = sys.argv[2:] or DATASETS
    results = json.loads(out.read_text()) if out.exists() else {}
    for name in names:
        cfg = load_config(str(CONFIGS / f"{name}.yaml"))
        train_df, test_df = dataset.load_split(cfg)
        for model, predict in PREDICTORS.items():
            if model in results.get(name, {}):
                continue
            run_cfg = copy.deepcopy(cfg)
            run_cfg["audit"]["repeated_seed_count"] = SEEDS[model]
            reuse_removal.fit_and_predict = predict
            started = time.time()
            finding = reuse_removal.check(train_df, test_df, run_cfg)
            finding["details"]["model"] = model
            finding["details"]["seconds"] = round(time.time() - started)
            results.setdefault(name, {})[model] = finding
            out.write_text(json.dumps(results, indent=2) + "\n")
            print(name, model, finding["status"], finding["summary"][:300], flush=True)


if __name__ == "__main__":
    main()
