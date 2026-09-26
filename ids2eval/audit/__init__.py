"""Data-quality audit checks: Paper 1's methodology as reusable code.

v1 checks need no external reference data; v2 checks (synthetic_realism_check,
cross_dataset_drift_check) need audit.reference_dataset, and known_issue_lookup
is a curated per-dataset lookup table needing neither.

Each check function returns a Finding dict: {check, status, summary, details}.
status is one of "ok" (nothing notable), "warning" (worth a human look), or
"flag" (a specific, checkable signature of a real data-quality problem).

STRUCTURAL_CHECKS are checks whose result cannot depend on
preprocessing.dedup: known_issue_lookup looks only at dataset.name,
schema_fingerprint_check only at column names (dedup removes rows, never
columns), and resplit_falsification/scenario_holdout_falsification both
reload the raw data themselves and never look at the train_df/test_df
they're passed. Run once, on the raw data; run_audit's caller (cli.py)
reuses that result instead of recomputing an answer that is guaranteed
identical the second time.
"""

from __future__ import annotations

import pandas as pd

from . import (
    class_distribution,
    cross_capture_matrix,
    cross_dataset_drift,
    data_integrity,
    dedup,
    flow_group_leakage,
    homogeneity,
    identity_columns,
    known_issues,
    label_conflict,
    leakage,
    near_duplicate_class,
    one_rule,
    port_protocol_shortcut,
    resplit,
    row_order_leakage,
    scenario_holdout,
    schema_fingerprint,
    seed_sensitivity,
    synthetic_realism,
    temporal_leakage,
    temporal_realism,
)

STRUCTURAL_CHECKS = frozenset({
    "known_issue_lookup", "schema_fingerprint_check", "resplit_falsification",
    "scenario_holdout_falsification", "cross_capture_matrix_check",
})

# A strict subset of STRUCTURAL_CHECKS: checks that report a documented, curated fact
# about the dataset or the tool that extracted it (a published labelling error, a
# known-buggy extractor), rather than measuring something about this run's actual
# data. resplit_falsification is structural too, but it measures this run's own split
# methodology and IS actionable (switch dataset.split_mode to "grouped"), so it stays
# out of this set and is reported alongside the other audit checks, not here.
KNOWN_ISSUE_CHECKS = frozenset({"known_issue_lookup", "schema_fingerprint_check"})

# Evidence basis for a check's result, fixed per check name, not computed per
# run: a citation needs a consistent answer to "how sure is this" for the
# same check every time, not a judgment that could vary run to run.
# "documented": a citation lookup against dataset.name or column names, not
# computed from this run's data at all.
# "direct-experiment": an actual counterfactual refit and comparison.
# "statistical": a threshold or hypothesis test against this run's data,
# with no independent corroboration. The default for anything not listed.
# A fourth level, "cross-corroborated", is not a per-check label: it applies
# only when homogeneity_test and resplit_falsification both flag on the
# same run, and is computed once at scorecard-build time from those two
# already-computed statuses (see ids2eval.reporting.scorecard).
EVIDENCE_LEVEL = {
    "known_issue_lookup": "documented",
    "schema_fingerprint_check": "documented",
    "resplit_falsification": "direct-experiment",
    "scenario_holdout_falsification": "direct-experiment",
    "cross_capture_matrix_check": "direct-experiment",
}
DEFAULT_EVIDENCE_LEVEL = "statistical"


def run_audit(
    train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict, skip: frozenset[str] = frozenset()
) -> list[dict]:
    """Run every audit check enabled in cfg['audit'] and not in `skip`, in schema order.

    Call this on the split BEFORE preprocessing.dedup is applied.
    dedup_check reports duplication already present in train_df/test_df,
    if the caller already deduplicated, it will always report zero.

    `skip` exists for the caller to omit STRUCTURAL_CHECKS on a second call
    with the same cfg (e.g. cli.py's after-dedup pass) - their answer can't
    change, so recomputing them (including resplit_falsification's two
    RandomForest fits) would be pure wasted work.
    """
    findings = []
    audit_cfg = cfg["audit"]
    if audit_cfg["dedup_check"] and "dedup_check" not in skip:
        findings.append(dedup.check(train_df, test_df, cfg))
    if audit_cfg["label_conflict_check"] and "label_conflict_check" not in skip:
        findings.append(label_conflict.check(train_df, test_df, cfg))
    if audit_cfg["near_duplicate_class_check"] and "near_duplicate_class_check" not in skip:
        findings.append(near_duplicate_class.check(train_df, cfg))
    if audit_cfg["leakage_screen"] and "leakage_screen" not in skip:
        findings.append(leakage.check(train_df, test_df, cfg))
    if audit_cfg["one_rule_check"] and "one_rule_check" not in skip:
        findings.append(one_rule.check(train_df, test_df, cfg))
    if audit_cfg["identity_column_flag"] and "identity_column_flag" not in skip:
        findings.append(identity_columns.check_predictive_power(train_df, test_df, cfg))
    if audit_cfg["port_protocol_shortcut_check"] and "port_protocol_shortcut_check" not in skip:
        findings.append(port_protocol_shortcut.check(train_df, test_df, cfg))
    if audit_cfg["temporal_leakage_check"] and "temporal_leakage_check" not in skip:
        findings.append(temporal_leakage.check(train_df, test_df, cfg))
    if audit_cfg["temporal_realism_check"] and "temporal_realism_check" not in skip:
        findings.append(temporal_realism.check(train_df, cfg))
    if audit_cfg["flow_group_leakage_check"] and "flow_group_leakage_check" not in skip:
        findings.append(flow_group_leakage.check(train_df, test_df, cfg))
    if audit_cfg["row_order_leakage_check"] and "row_order_leakage_check" not in skip:
        findings.append(row_order_leakage.check(train_df, test_df, cfg))
    if audit_cfg["homogeneity_test"] and "homogeneity_test" not in skip:
        findings.append(homogeneity.check(train_df, test_df, cfg))
    if audit_cfg["resplit_falsification"] and "resplit_falsification" not in skip:
        findings.append(resplit.check(cfg))
    if audit_cfg["scenario_holdout_falsification"] and "scenario_holdout_falsification" not in skip:
        findings.append(scenario_holdout.check(cfg))
    if audit_cfg["class_distribution_report"] and "class_distribution_report" not in skip:
        findings.append(class_distribution.check(train_df, test_df, cfg))
    if audit_cfg["low_cardinality_warning"] and "low_cardinality_warning" not in skip:
        findings.append(identity_columns.check_cardinality(train_df, cfg))
    if audit_cfg["schema_fingerprint_check"] and "schema_fingerprint_check" not in skip:
        findings.append(schema_fingerprint.check(train_df, cfg))
    if audit_cfg["data_integrity_check"] and "data_integrity_check" not in skip:
        findings.append(data_integrity.check(train_df, cfg))
    if audit_cfg["synthetic_realism_check"] and "synthetic_realism_check" not in skip:
        findings.append(synthetic_realism.check(train_df, cfg))
    if audit_cfg["cross_dataset_drift_check"] and "cross_dataset_drift_check" not in skip:
        findings.append(cross_dataset_drift.check(train_df, test_df, cfg))
    if audit_cfg["cross_capture_matrix_check"] and "cross_capture_matrix_check" not in skip:
        findings.append(cross_capture_matrix.check(cfg))
    if audit_cfg["known_issue_lookup"] and "known_issue_lookup" not in skip:
        findings.append(known_issues.check(train_df, cfg))
    if audit_cfg["seed_sensitivity_check"] and "seed_sensitivity_check" not in skip:
        findings.append(seed_sensitivity.check(train_df, test_df, cfg))
    return findings
