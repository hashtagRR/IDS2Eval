"""Load and validate IDS2Eval YAML configs against configs/schema.yaml."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

VALID_CLASSIFIERS = {
    "RandomForest", "XGBoost", "DecisionTree", "NaiveBayes",
    "LogisticRegression", "KNN", "SVM", "LDA", "Stacking", "Voting",
    "ExtraTrees", "HistGradientBoosting", "AdaBoost", "MLP",
}
NO_TUNE_CLASSIFIERS = {"NaiveBayes", "Stacking", "Voting"}

VALID_SAMPLING = {"none", "smote", "smoteenn", "enn", "random_undersample"}
VALID_SCALING = {"none", "standard", "minmax", "robust"}
VALID_SPLIT_MODE = {"random", "grouped"}
VALID_CALIBRATION = {"none", "platt", "isotonic"}
VALID_OUTPUT_FORMAT = {"parquet", "csv"}

DEFAULTS: dict[str, Any] = {
    "dataset": {
        "name": None,
        "raw_files": [],
        "train_file": None,
        "test_file": None,
        "split_ratio": 0.8,
        "split_mode": "random",
        "group_columns": [],
        "chunk_size": None,
        "max_rows": None,
    },
    "schema": {
        "label_column": None,
        "attack_category_column": None,
        "drop_columns": [],
        "id_like_columns": [],
    },
    "label_grouping": {
        "attack_type_mapping": {},
    },
    "preprocessing": {
        "dedup": True,
        "scaling": "standard",
        "sampling": {"binary": "none", "type": "none"},
    },
    "audit": {
        "dedup_check": True,
        "leakage_screen": True,
        "identity_column_flag": True,
        "homogeneity_test": True,
        "resplit_falsification": True,
        "class_distribution_report": True,
        "low_cardinality_warning": True,
        "schema_fingerprint_check": True,
        "synthetic_realism_check": False,
        "cross_dataset_drift_check": False,
        "known_issue_lookup": False,
        "reference_dataset": None,
    },
    "classifiers": {
        "list": "all",
        "tuning": False,
        "calibration": "none",
        "hyperparameters": {},
        "search_space": {},
    },
    "output": {
        "dir": "./output",
        "format": "parquet",
        "save_preprocessed": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        user_cfg = yaml.safe_load(f) or {}
    cfg = _deep_merge(DEFAULTS, user_cfg)
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    errors: list[str] = []

    dataset = cfg["dataset"]
    has_raw = bool(dataset["raw_files"])
    has_presplit = bool(dataset["train_file"] and dataset["test_file"])
    if not dataset["name"]:
        errors.append("dataset.name is required")
    if has_raw == has_presplit:
        errors.append(
            "dataset must specify exactly one of raw_files, or train_file+test_file together"
        )
    if dataset["split_mode"] not in VALID_SPLIT_MODE:
        errors.append(f"dataset.split_mode must be one of {sorted(VALID_SPLIT_MODE)}")
    if dataset["split_mode"] == "grouped" and not dataset["group_columns"]:
        errors.append("dataset.group_columns is required when split_mode is 'grouped'")
    if dataset["chunk_size"] is not None and dataset["chunk_size"] <= 0:
        errors.append("dataset.chunk_size must be a positive integer")
    if dataset["max_rows"] is not None:
        if dataset["max_rows"] <= 0:
            errors.append("dataset.max_rows must be a positive integer")
        if not dataset["chunk_size"]:
            errors.append(
                "dataset.max_rows requires dataset.chunk_size to be set — reservoir "
                "sampling still has to read the file in chunks to sample it"
            )

    if not cfg["schema"]["label_column"]:
        errors.append("schema.label_column is required")

    scaling = cfg["preprocessing"]["scaling"]
    if scaling not in VALID_SCALING:
        errors.append(f"preprocessing.scaling must be one of {sorted(VALID_SCALING)}")
    for stage, algo in cfg["preprocessing"]["sampling"].items():
        if algo not in VALID_SAMPLING:
            errors.append(
                f"preprocessing.sampling.{stage} must be one of {sorted(VALID_SAMPLING)}"
            )

    audit = cfg["audit"]
    v2_checks = ["synthetic_realism_check", "cross_dataset_drift_check", "known_issue_lookup"]
    if any(audit[check] for check in v2_checks) and not audit["reference_dataset"]:
        errors.append(
            f"audit.reference_dataset is required when any of {v2_checks} is true"
        )
    if audit["resplit_falsification"] and not (has_raw and dataset["group_columns"]):
        errors.append(
            "audit.resplit_falsification requires dataset.raw_files (it builds its "
            "own independent random-vs-grouped comparison split) and dataset.group_columns "
            "— it cannot run against a pre-split train_file/test_file pair"
        )

    classifiers = cfg["classifiers"]
    clf_list = classifiers["list"]
    if clf_list != "all":
        unknown = set(clf_list) - VALID_CLASSIFIERS
        if unknown:
            errors.append(
                f"classifiers.list has unknown entries {sorted(unknown)}; "
                f"valid options are {sorted(VALID_CLASSIFIERS)}"
            )
    unknown_hp = set(classifiers["hyperparameters"]) - VALID_CLASSIFIERS
    if unknown_hp:
        errors.append(f"classifiers.hyperparameters has unknown classifier names {sorted(unknown_hp)}")
    unknown_ss = set(classifiers["search_space"]) - VALID_CLASSIFIERS
    if unknown_ss:
        errors.append(f"classifiers.search_space has unknown classifier names {sorted(unknown_ss)}")
    if classifiers["calibration"] not in VALID_CALIBRATION:
        errors.append(f"classifiers.calibration must be one of {sorted(VALID_CALIBRATION)}")

    if cfg["output"]["format"] not in VALID_OUTPUT_FORMAT:
        errors.append(f"output.format must be one of {sorted(VALID_OUTPUT_FORMAT)}")

    if errors:
        raise ValueError("Invalid config:\n" + "\n".join(f"  - {e}" for e in errors))
