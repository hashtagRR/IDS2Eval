"""Scenario-holdout falsification.

resplit_falsification asks whether session-correlated leakage crosses
a random split's boundary; this asks a different, complementary
question: does high random-split accuracy survive never having seen an
entire collection scenario (a capture day, an attacker machine, a
scenario label, whatever schema.scenario_column names) during training
at all? Compares random-split accuracy against holding out the single
scenario value with the fewest rows entirely as test, training on
every other scenario. A model that only memorized capture-environment
artifacts (Monday's specific traffic mix, one attacker host's quirks)
rather than attack behavior in general should collapse on a scenario
it never trained on; a model that learned the actual behavior should
not.

Some accuracy drop under a genuinely novel scenario is expected even
from a clean dataset, generalizing to conditions never seen in training
is a harder problem than a random split of the same conditions, so the
material-drop threshold here is deliberately looser than
resplit_falsification's: this test is falsifying "the model learned
attack behavior," not "there is zero session-correlated leakage."

Needs dataset.raw_files (like resplit_falsification, it builds its own
comparison split from the raw data) and schema.scenario_column; no-ops
otherwise, since scenario_column has no universal name to detect
automatically.
"""

from __future__ import annotations

from ..data import dataset
from ._fit_score import fit_and_score

MATERIAL_DROP_THRESHOLD = 0.10
WARNING_DROP_THRESHOLD = 0.05
MIN_HOLDOUT_ROWS = 20


def check(cfg: dict) -> dict:
    dataset_cfg = cfg["dataset"]
    scenario_col = cfg["schema"]["scenario_column"]
    if not scenario_col:
        return {
            "check": "scenario_holdout_falsification", "status": "ok",
            "summary": "no schema.scenario_column configured", "details": {},
        }
    if not dataset_cfg["raw_files"]:
        return {
            "check": "scenario_holdout_falsification", "status": "ok",
            "summary": "requires dataset.raw_files, not applicable to a pre-split train_file/test_file pair",
            "details": {},
        }

    label_col = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(dataset_cfg)
    if scenario_col not in combined.columns:
        return {
            "check": "scenario_holdout_falsification", "status": "ok",
            "summary": f"'{scenario_col}' not found in the loaded data", "details": {},
        }

    scenario_counts = combined[scenario_col].value_counts()
    if len(scenario_counts) < 2:
        return {
            "check": "scenario_holdout_falsification", "status": "ok",
            "summary": "fewer than two distinct scenarios to hold one out against", "details": {},
        }

    held_out = scenario_counts.index[-1]  # the smallest scenario, cheapest to hold out
    held_out_mask = combined[scenario_col] == held_out
    scenario_test = combined[held_out_mask]
    scenario_train = combined[~held_out_mask]
    if len(scenario_test) < MIN_HOLDOUT_ROWS or scenario_train[label_col].nunique() < 2:
        return {
            "check": "scenario_holdout_falsification", "status": "ok",
            "summary": f"scenario '{held_out}' has too few rows or labels to test", "details": {},
        }

    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg)
    random_acc = fit_and_score(random_train, random_test, label_col, cfg)
    scenario_acc = fit_and_score(scenario_train, scenario_test, label_col, cfg)
    drop = random_acc - scenario_acc

    if drop > MATERIAL_DROP_THRESHOLD:
        status = "flag"
    elif drop > WARNING_DROP_THRESHOLD:
        status = "warning"
    else:
        status = "ok"

    summary = (
        f"random-split accuracy={random_acc:.4f}, holding out scenario '{held_out}' entirely: "
        f"accuracy={scenario_acc:.4f} (drop={drop:+.4f})"
    )
    if status == "flag":
        summary += "; accuracy collapses on a scenario never seen in training"
    elif status == "warning":
        summary += "; a real but moderate drop under a novel scenario"

    return {
        "check": "scenario_holdout_falsification", "status": status, "summary": summary,
        "details": {
            "held_out_scenario": str(held_out), "random_accuracy": random_acc,
            "scenario_accuracy": scenario_acc, "drop": drop,
        },
    }
