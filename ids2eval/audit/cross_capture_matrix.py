"""Cross-capture generalization matrix (v2, opt-in).

scenario_holdout_falsification reports one number: accuracy when the
single smallest scenario is held out entirely. That can't distinguish
"generalization to any unseen scenario is genuinely hard here" from
"this one specific pair of scenarios is asymmetric": training on
scenario A and testing on B might collapse while the reverse does not,
invisible in a single holdout figure. This trains on each declared
scenario (schema.scenario_column) and tests on every other one,
producing the full N x N accuracy matrix instead.

Real, not negligible, compute: N*(N-1) RandomForest fits rather than
scenario_holdout_falsification's one, so this is opt-in and capped at
MAX_SCENARIOS scenarios, skipped rather than run past that cap. Same
raw-data reload as resplit_falsification/scenario_holdout_falsification,
so its result cannot depend on preprocessing.dedup either.
"""

from __future__ import annotations

from ..data import dataset
from ._fit_score import fit_and_score

MAX_SCENARIOS = 6
MIN_SCENARIO_ROWS = 20
SPREAD_FLAG_THRESHOLD = 0.20
SPREAD_WARNING_THRESHOLD = 0.10


def check(cfg: dict) -> dict:
    dataset_cfg = cfg["dataset"]
    scenario_col = cfg["schema"]["scenario_column"]
    if not scenario_col:
        return {
            "check": "cross_capture_matrix_check", "status": "ok",
            "summary": "no schema.scenario_column configured", "details": {},
        }
    if not dataset_cfg["raw_files"]:
        return {
            "check": "cross_capture_matrix_check", "status": "ok",
            "summary": "requires dataset.raw_files, not applicable to a pre-split train_file/test_file pair",
            "details": {},
        }

    label_col = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(dataset_cfg)
    if scenario_col not in combined.columns:
        return {
            "check": "cross_capture_matrix_check", "status": "ok",
            "summary": f"'{scenario_col}' not found in the loaded data", "details": {},
        }

    counts = combined[scenario_col].value_counts()
    eligible = counts[counts >= MIN_SCENARIO_ROWS].index.tolist()
    if len(eligible) < 2:
        return {
            "check": "cross_capture_matrix_check", "status": "ok",
            "summary": "fewer than two scenarios with enough rows to build a matrix", "details": {},
        }
    if len(eligible) > MAX_SCENARIOS:
        return {
            "check": "cross_capture_matrix_check", "status": "ok",
            "summary": f"skipped, {len(eligible)} eligible scenarios exceeds the {MAX_SCENARIOS}-scenario cap",
            "details": {},
        }

    matrix = {}
    for train_scenario in eligible:
        train_part = combined[combined[scenario_col] == train_scenario]
        if train_part[label_col].nunique() < 2:
            continue
        for test_scenario in eligible:
            if test_scenario == train_scenario:
                continue
            test_part = combined[combined[scenario_col] == test_scenario]
            matrix[f"{train_scenario}->{test_scenario}"] = fit_and_score(
                train_part, test_part, label_col, cfg
            )

    if not matrix:
        return {
            "check": "cross_capture_matrix_check", "status": "ok",
            "summary": "no scenario pair had enough distinct labels to test", "details": {},
        }

    worst_pair, worst_acc = min(matrix.items(), key=lambda kv: kv[1])
    best_pair, best_acc = max(matrix.items(), key=lambda kv: kv[1])
    spread = best_acc - worst_acc

    if spread > SPREAD_FLAG_THRESHOLD:
        status = "flag"
    elif spread > SPREAD_WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "ok"

    summary = (
        f"cross-scenario accuracy ranges from {worst_acc:.4f} ({worst_pair}) to "
        f"{best_acc:.4f} ({best_pair}), a spread of {spread:.4f} across {len(matrix)} scenario pairs"
    )
    if status != "ok":
        summary += "; generalization across scenarios is uneven rather than uniformly hard or easy"

    return {
        "check": "cross_capture_matrix_check", "status": status, "summary": summary,
        "details": {"matrix": matrix, "worst_pair": worst_pair, "best_pair": best_pair, "spread": spread},
    }
