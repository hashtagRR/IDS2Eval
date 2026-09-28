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

# Which checks support audit.materiality_thresholds overrides, and the shape each one
# expects: a single number for a binary flag/ok check, or the two named tiers for a
# check with a three-tier ok/warning/flag scale. Kept here as the one place that has to
# stay in sync with which checks actually call ids2eval.audit._materiality.threshold().
MATERIALITY_SINGLE_CHECKS = {
    "resplit_falsification", "cross_dataset_drift_check", "repeated_seed_falsification_check",
}
MATERIALITY_TIERED_CHECKS = {
    "result_robustness_check", "cross_capture_matrix_check",
    "scenario_holdout_falsification", "feature_category_ablation_check",
}

DEFAULTS: dict[str, Any] = {
    "random_seed": 0,      # every random_state/seed in the pipeline (split, reservoir
                            # sampling, SMOTE/etc., classifier init, benchmark subsampling)
                            # derives from this one value, so a run is reproducible from
                            # resolved_config.json alone rather than 6 scattered constants
    "dataset": {
        "name": None,
        "raw_files": [],
        "train_file": None,
        "test_file": None,
        "column_names": [],
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
        "timestamp_column": None,
        "flow_id_columns": [],
        "scenario_column": None,
        "feature_categories": {},
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
        "label_conflict_check": True,
        "near_duplicate_class_check": True,
        "leakage_screen": True,
        "one_rule_check": True,
        "feature_auc_ranking_check": True,
        "identity_column_flag": True,
        "port_protocol_shortcut_check": True,
        "temporal_leakage_check": True,
        "temporal_realism_check": True,
        "flow_group_leakage_check": True,
        "row_order_leakage_check": True,
        "homogeneity_test": True,
        "resplit_falsification": True,
        "scenario_holdout_falsification": True,
        "class_distribution_report": True,
        "low_cardinality_warning": True,
        "schema_fingerprint_check": True,
        "data_integrity_check": True,
        "synthetic_realism_check": False,
        "cross_dataset_drift_check": False,
        "cross_capture_matrix_check": False,
        "feature_category_ablation_check": False,
        "artifact_sensitivity_check": False,
        "result_robustness_check": False,
        "known_issue_lookup": False,
        "seed_sensitivity_check": False,
        "repeated_seed_falsification_check": False,
        # Number of independent seeds repeated_seed_falsification_check refits under;
        # each additional seed is a full pair of RandomForest refits on the whole raw
        # dataset, real, non-negligible compute on a large dataset, hence opt-in above.
        "repeated_seed_count": 10,
        "reference_dataset": None,
        # Per-check materiality thresholds, frozen and user-visible rather than a buried
        # module constant. Empty by default: each check keeps its own already-calibrated
        # default (see the check's own module) unless overridden here by check name. A
        # single number for a binary flag/ok check (e.g. resplit_falsification: 0.01), or
        # {"warning": x, "flag": y} for a check with a three-tier ok/warning/flag scale
        # (e.g. result_robustness_check). Deliberately per-check, not one global value:
        # resplit_falsification's 0.01 and feature_category_ablation_check's 0.30 measure
        # very different things (any session-leakage cost vs. expected ablation cost) and
        # were each calibrated to their own check's scale.
        "materiality_thresholds": {},
        # Off by default: running checks concurrently means several may hold their own
        # encoded feature matrix/RandomForest fit in memory at the same time instead of
        # one at a time, raising peak memory versus the sequential default - a real
        # concern on large-scale runs sized against sequential peak usage. Opt in once a
        # run's VM has memory headroom to spare; max_parallel_checks caps how many run
        # at once so this can't silently spike to running all ~28 checks simultaneously.
        "parallel_checks": False,
        "max_parallel_checks": 4,
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
        "keep_runs": 10,
        "write_scorecard_plot": False,
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


def apply_patch(cfg: dict, patch: dict) -> dict:
    """Deep-merge a partial config (e.g. a reporting.recommend patch) onto an
    already-resolved config. A list in `patch` replaces the corresponding
    list in `cfg` wholesale, it is never concatenated.
    """
    return _deep_merge(cfg, patch)


def load_config(path: str | Path) -> dict[str, Any]:
    try:
        with open(path) as f:
            user_cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ValueError(
            f"Config file not found: {path}. See configs/README.md in the repo for every "
            "field, or the Quick start section of README.md for a minimal example."
        ) from None
    cfg = _deep_merge(DEFAULTS, user_cfg)
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    errors: list[str] = []

    if not isinstance(cfg["random_seed"], int) or isinstance(cfg["random_seed"], bool):
        errors.append("random_seed must be an integer")

    dataset = cfg["dataset"]
    has_raw = bool(dataset["raw_files"])
    has_presplit = bool(dataset["train_file"] and dataset["test_file"])
    if not dataset["name"]:
        errors.append("dataset.name is required")
    if has_raw == has_presplit:
        errors.append(
            "dataset must specify exactly one of raw_files, or train_file+test_file together"
        )
    split_ratio = dataset["split_ratio"]
    if not isinstance(split_ratio, (int, float)) or isinstance(split_ratio, bool) or not 0 < split_ratio < 1:
        errors.append("dataset.split_ratio must be a number strictly between 0 and 1")
    if dataset["split_mode"] not in VALID_SPLIT_MODE:
        errors.append(f"dataset.split_mode must be one of {sorted(VALID_SPLIT_MODE)}")
    if dataset["split_mode"] == "grouped" and not dataset["group_columns"]:
        errors.append("dataset.group_columns is required when split_mode is 'grouped'")
    column_names = dataset["column_names"]
    if column_names:
        if not isinstance(column_names, list) or not all(isinstance(c, str) for c in column_names):
            errors.append("dataset.column_names must be a list of strings")
        elif len(column_names) != len(set(column_names)):
            dupes = sorted({c for c in column_names if column_names.count(c) > 1})
            errors.append(f"dataset.column_names has duplicate name(s): {dupes}")
    if dataset["chunk_size"] is not None and dataset["chunk_size"] <= 0:
        errors.append("dataset.chunk_size must be a positive integer")
    if dataset["max_rows"] is not None:
        if dataset["max_rows"] <= 0:
            errors.append("dataset.max_rows must be a positive integer")
        if not dataset["chunk_size"]:
            errors.append(
                "dataset.max_rows requires dataset.chunk_size to be set. Reservoir "
                "sampling still has to read the file in chunks to sample it"
            )

    if not cfg["schema"]["label_column"]:
        errors.append("schema.label_column is required")
    if cfg["label_grouping"]["attack_type_mapping"] and not cfg["schema"]["attack_category_column"]:
        errors.append(
            "label_grouping.attack_type_mapping requires schema.attack_category_column "
            "to be set, otherwise there's no column for it to apply to"
        )

    scaling = cfg["preprocessing"]["scaling"]
    scalings = scaling if isinstance(scaling, list) else [scaling]
    invalid_scaling = [s for s in scalings if s not in VALID_SCALING]
    if invalid_scaling:
        errors.append(
            f"preprocessing.scaling has invalid entries {invalid_scaling}; "
            f"each must be one of {sorted(VALID_SCALING)}"
        )
    if not scalings:
        errors.append("preprocessing.scaling must not be an empty list")
    for stage, algo in cfg["preprocessing"]["sampling"].items():
        algos = algo if isinstance(algo, list) else [algo]
        invalid = [a for a in algos if a not in VALID_SAMPLING]
        if invalid:
            errors.append(
                f"preprocessing.sampling.{stage} has invalid entries {invalid}; "
                f"each must be one of {sorted(VALID_SAMPLING)}"
            )
        if not algos:
            errors.append(f"preprocessing.sampling.{stage} must not be an empty list")

    audit = cfg["audit"]
    # known_issue_lookup is a pure curated-table lookup keyed on dataset.name,
    # unlike the other two v2 checks, it needs no second dataset to compare against.
    reference_needing_checks = ["synthetic_realism_check", "cross_dataset_drift_check"]
    if any(audit[check] for check in reference_needing_checks) and not audit["reference_dataset"]:
        errors.append(
            f"audit.reference_dataset is required when any of {reference_needing_checks} is true"
        )
    # repeated_seed_falsification_check shares resplit_falsification's exact precondition:
    # it's the same random-vs-grouped comparison, just repeated across seeds.
    for check_name in ("resplit_falsification", "repeated_seed_falsification_check"):
        if audit[check_name] and not (has_raw and dataset["group_columns"]):
            if not has_raw:
                errors.append(
                    f"audit.{check_name} needs dataset.raw_files, not a pre-split "
                    "train_file/test_file pair (it builds its own independent random-vs-"
                    f"grouped comparison split from the raw data). Set "
                    f"audit.{check_name}: false if this dataset has no "
                    "session-identifying columns to group by."
                )
            else:
                errors.append(
                    f"audit.{check_name} needs dataset.group_columns set (e.g. "
                    "source/destination IP and port, or whatever identifies a session in "
                    f"this dataset) to build its grouped-split comparison. Set "
                    f"audit.{check_name}: false instead if this dataset has no "
                    "such columns, see guide/checks.md for what the check does."
                )

    n_seeds = audit["repeated_seed_count"]
    if isinstance(n_seeds, bool) or not isinstance(n_seeds, int) or n_seeds < 1:
        errors.append("audit.repeated_seed_count must be a positive integer")

    if not isinstance(audit["parallel_checks"], bool):
        errors.append("audit.parallel_checks must be true or false")
    max_parallel = audit["max_parallel_checks"]
    if isinstance(max_parallel, bool) or not isinstance(max_parallel, int) or max_parallel < 1:
        errors.append("audit.max_parallel_checks must be a positive integer")

    thresholds = audit["materiality_thresholds"]
    known_threshold_checks = MATERIALITY_SINGLE_CHECKS | MATERIALITY_TIERED_CHECKS
    unknown_threshold_checks = set(thresholds) - known_threshold_checks
    if unknown_threshold_checks:
        errors.append(
            f"audit.materiality_thresholds has entries for {sorted(unknown_threshold_checks)}, "
            f"which don't support a threshold override; valid keys are {sorted(known_threshold_checks)}"
        )
    for check in MATERIALITY_SINGLE_CHECKS & set(thresholds):
        if isinstance(thresholds[check], bool) or not isinstance(thresholds[check], (int, float)):
            errors.append(
                f"audit.materiality_thresholds.{check} must be a single number "
                f"(this check has one flag/ok threshold, not separate warning/flag tiers)"
            )
    for check in MATERIALITY_TIERED_CHECKS & set(thresholds):
        value = thresholds[check]
        if not isinstance(value, dict) or set(value) != {"warning", "flag"}:
            errors.append(
                f'audit.materiality_thresholds.{check} must be a dict with exactly the keys '
                f'"warning" and "flag" (this check has a three-tier ok/warning/flag scale)'
            )
        elif not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value.values()):
            errors.append(f"audit.materiality_thresholds.{check}'s warning and flag values must be numbers")
        elif value["warning"] >= value["flag"]:
            errors.append(
                f"audit.materiality_thresholds.{check}.warning ({value['warning']}) must be "
                f"less than .flag ({value['flag']})"
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
    keep_runs = cfg["output"]["keep_runs"]
    if keep_runs is not None and keep_runs <= 0:
        errors.append("output.keep_runs must be a positive integer, or null to keep all runs")

    if cfg["output"]["write_scorecard_plot"]:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            errors.append(
                "output.write_scorecard_plot is true but matplotlib isn't installed. "
                'run: pip install "ids2eval[plots]"'
            )

    if errors:
        raise ValueError("Invalid config:\n" + "\n".join(f"  - {e}" for e in errors))
