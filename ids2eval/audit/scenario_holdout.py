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
from . import _metrics
from ._fit_score import fit_and_evaluate
from ._status import NOT_APPLICABLE

# Overridable via audit.materiality_thresholds.scenario_holdout_falsification
# ({"warning": .., "flag": ..}).
MATERIAL_DROP_THRESHOLD = 0.10
WARNING_DROP_THRESHOLD = 0.05
MIN_HOLDOUT_ROWS = 20


def check(cfg: dict) -> dict:
    dataset_cfg = cfg["dataset"]
    scenario_col = cfg["schema"]["scenario_column"]
    if not scenario_col:
        return {
            "check": "scenario_holdout_falsification", "status": NOT_APPLICABLE,
            "summary": "no schema.scenario_column configured", "details": {},
        }
    if not dataset_cfg["raw_files"]:
        return {
            "check": "scenario_holdout_falsification", "status": NOT_APPLICABLE,
            "summary": "requires dataset.raw_files, not applicable to a pre-split train_file/test_file pair",
            "details": {},
        }

    seed = cfg["random_seed"]
    label_col = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(dataset_cfg, seed=seed)
    if scenario_col not in combined.columns:
        return {
            "check": "scenario_holdout_falsification", "status": NOT_APPLICABLE,
            "summary": f"'{scenario_col}' not found in the loaded data", "details": {},
        }

    scenario_counts = combined[scenario_col].value_counts()
    if len(scenario_counts) < 2:
        return {
            "check": "scenario_holdout_falsification", "status": NOT_APPLICABLE,
            "summary": "fewer than two distinct scenarios to hold one out against", "details": {},
        }

    held_out = scenario_counts.index[-1]  # the smallest scenario, cheapest to hold out
    held_out_mask = combined[scenario_col] == held_out
    scenario_test = combined[held_out_mask]
    scenario_train = combined[~held_out_mask]
    if len(scenario_test) < MIN_HOLDOUT_ROWS or scenario_train[label_col].nunique() < 2:
        return {
            "check": "scenario_holdout_falsification", "status": NOT_APPLICABLE,
            "summary": f"scenario '{held_out}' has too few rows or labels to test", "details": {},
        }

    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
    random_m = fit_and_evaluate(random_train, random_test, label_col, cfg, seed=seed).metrics
    scenario_m = fit_and_evaluate(scenario_train, scenario_test, label_col, cfg, seed=seed).metrics

    tiers = _metrics.thresholds(
        cfg, "scenario_holdout_falsification",
        {"warning": WARNING_DROP_THRESHOLD, "flag": MATERIAL_DROP_THRESHOLD},
    )
    drops = {m: random_m[m] - scenario_m[m] for m in _metrics.METRICS}
    verdicts = {m: _metrics.tiered_verdict(drops[m], tiers[m]) for m in _metrics.METRICS}
    status = _metrics.combined_status(verdicts, cfg)
    random_acc, scenario_acc, drop = random_m["accuracy"], scenario_m["accuracy"], drops["accuracy"]

    summary = (
        f"random-split accuracy={random_acc:.4f}, holding out scenario '{held_out}' entirely: "
        f"accuracy={scenario_acc:.4f} (drop={drop:+.4f}); balanced accuracy drop="
        f"{drops['balanced_accuracy']:+.4f}, macro-F1 drop={drops['macro_f1']:+.4f} "
        f"({_metrics.describe(verdicts)})"
    )
    if status == "flag":
        summary += "; performance collapses on a scenario never seen in training"
    elif status == "warning":
        summary += "; a real but moderate drop under a novel scenario"

    return {
        "check": "scenario_holdout_falsification", "status": status, "summary": summary,
        "details": {
            "held_out_scenario": str(held_out), "random_accuracy": random_acc,
            "scenario_accuracy": scenario_acc, "drop": drop,
            "by_metric": {
                m: {"random": random_m[m], "scenario": scenario_m[m], "drop": drops[m],
                    "thresholds": tiers[m], "verdict": verdicts[m]}
                for m in _metrics.METRICS
            },
            "materiality_metrics": list(cfg["audit"]["materiality_metrics"]),
        },
    }
