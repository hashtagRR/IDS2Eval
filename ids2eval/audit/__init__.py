"""Data-quality audit checks — Paper 1's methodology as reusable code.

v1 checks need no external reference data; v2 checks (synthetic_realism_check,
cross_dataset_drift_check) need audit.reference_dataset, and known_issue_lookup
is a curated per-dataset lookup table needing neither.

Each check function returns a Finding dict: {check, status, summary, details}.
status is one of "ok" (nothing notable), "warning" (worth a human look), or
"flag" (a specific, checkable signature of a real data-quality problem).
"""

from __future__ import annotations

import pandas as pd

from . import (
    class_distribution,
    cross_dataset_drift,
    data_integrity,
    dedup,
    homogeneity,
    identity_columns,
    known_issues,
    leakage,
    resplit,
    schema_fingerprint,
    synthetic_realism,
)


def run_audit(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> list[dict]:
    """Run every audit check enabled in cfg['audit'], in schema order.

    Call this on the split BEFORE preprocessing.dedup is applied.
    dedup_check reports duplication already present in train_df/test_df —
    if the caller already deduplicated, it will always report zero.
    """
    findings = []
    audit_cfg = cfg["audit"]
    if audit_cfg["dedup_check"]:
        findings.append(dedup.check(train_df, test_df, cfg))
    if audit_cfg["leakage_screen"]:
        findings.append(leakage.check(train_df, test_df, cfg))
    if audit_cfg["identity_column_flag"]:
        findings.append(identity_columns.check_predictive_power(train_df, test_df, cfg))
    if audit_cfg["homogeneity_test"]:
        findings.append(homogeneity.check(train_df, test_df, cfg))
    if audit_cfg["resplit_falsification"]:
        findings.append(resplit.check(cfg))
    if audit_cfg["class_distribution_report"]:
        findings.append(class_distribution.check(train_df, test_df, cfg))
    if audit_cfg["low_cardinality_warning"]:
        findings.append(identity_columns.check_cardinality(train_df, cfg))
    if audit_cfg["schema_fingerprint_check"]:
        findings.append(schema_fingerprint.check(train_df, cfg))
    if audit_cfg["data_integrity_check"]:
        findings.append(data_integrity.check(train_df, cfg))
    if audit_cfg["synthetic_realism_check"]:
        findings.append(synthetic_realism.check(train_df, cfg))
    if audit_cfg["cross_dataset_drift_check"]:
        findings.append(cross_dataset_drift.check(train_df, test_df, cfg))
    if audit_cfg["known_issue_lookup"]:
        findings.append(known_issues.check(train_df, cfg))
    return findings
