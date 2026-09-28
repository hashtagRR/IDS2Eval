"""Intervention manifest: reformats the checks that already ARE an
intervention (they refit under an altered condition and compare, rather
than measuring a static property of the data) into one structured record
per intervention, machine-readable, matching this project's own falsification
methodology directly rather than the ok/warning/flag scorecard's summary view.

This is a re-projection of findings IDS²Eval already computes, not a new
detection-and-selection engine: every check listed in INTERVENTION_CHECKS
always runs (or doesn't) according to audit.<check_name> in the config, the
same as every other check, rather than being dynamically triggered by a
prior finding's specific value. Building that latter, fuller "detect a
threat, then choose which intervention to run" rule engine is real,
larger, separate work this module does not attempt; what it does do is give
every intervention that DID run a citable, uniformly-shaped record.

Each record's four sections follow the shape:
    finding:      the check name, its status, and its own details dict as
                  evidence (heterogeneous by check, e.g. resplit_falsification's
                  random/grouped accuracy vs. feature_category_ablation_check's
                  per-category drop; kept as-is rather than forced into one
                  fixed evidence shape, which would lose information)
    intervention: what was done (a fixed, human-readable label per check)
                  and that it was performed (always true here, since the
                  record only exists for a check that actually ran)
    consequence:  the same details dict again, from the intervention's own
                  perspective - the "before" and "after" of a resplit-style
                  check are the same two numbers as its "evidence"
    conclusion:   "material" / "investigated_not_material" / "inconclusive",
                  reusing the check's own explicit `material` field
                  (True/False/None) when it has one (repeated_seed_falsification_
                  check), otherwise derived from its ok/warning/flag status
"""

from __future__ import annotations

# check name -> human-readable intervention label.
INTERVENTION_CHECKS = {
    "resplit_falsification": "session/time-grouped resplit",
    "repeated_seed_falsification_check": "session/time-grouped resplit, repeated across seeds",
    "scenario_holdout_falsification": "held out one entire scenario from training",
    "cross_capture_matrix_check": "trained on each scenario, tested on every other",
    "feature_category_ablation_check": "removed one declared feature category and refit",
    "cross_dataset_drift_check": "trained here, evaluated on an independent reference dataset",
    "result_robustness_check": "refit under each buildable condition (split, dedup, identity columns)",
    "artifact_sensitivity_check": "reshuffled one declared identity/timestamp column's values and re-predicted",
}

_STATUS_TO_CONCLUSION = {"flag": "material", "warning": "inconclusive", "ok": "investigated_not_material"}


def _conclusion_status(finding: dict) -> str:
    material = finding.get("details", {}).get("material")
    if material is True:
        return "material"
    if material is False:
        return "investigated_not_material"
    if material is None and "material" in finding.get("details", {}):
        return "inconclusive"  # explicit tri-state field said "can't tell", not just absent
    return _STATUS_TO_CONCLUSION[finding["status"]]


def build_manifest(findings: list[dict]) -> list[dict]:
    """One record per finding in `findings` whose check is in INTERVENTION_CHECKS
    AND actually ran, not a no-op. Every check here returns `"details": {}` for its
    no-op case (schema.scenario_column/reference_dataset/etc. not configured, or no
    candidate columns present) - confirmed real against a live run where
    scenario_holdout_falsification's no-op ("no schema.scenario_column configured")
    would otherwise have shown up as intervention.performed: true, a real bug this
    empty-details check exists specifically to prevent from recurring.
    """
    records = []
    for finding in findings:
        check = finding["check"]
        if check not in INTERVENTION_CHECKS or not finding.get("details"):
            continue
        records.append({
            "finding": {"check": check, "status": finding["status"], "evidence": finding.get("details", {})},
            "intervention": {"type": check, "description": INTERVENTION_CHECKS[check], "performed": True},
            "consequence": finding.get("details", {}),
            "conclusion": {"status": _conclusion_status(finding)},
        })
    return records
