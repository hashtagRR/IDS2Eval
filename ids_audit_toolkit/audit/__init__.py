"""v1 data-quality audit checks — Paper 1's methodology as reusable code.

Each check function returns a Finding dict: {check, status, summary, details}.
status is one of "ok" (nothing notable), "warning" (worth a human look), or
"flag" (a specific, checkable signature of a real data-quality problem).
"""

from __future__ import annotations

import pandas as pd

from . import class_distribution, dedup, homogeneity, identity_columns, leakage, resplit, schema_fingerprint

CHECK_MODULES = {
    "dedup_check": dedup,
    "leakage_screen": leakage,
    "identity_column_flag": identity_columns,
    "homogeneity_test": homogeneity,
    "resplit_falsification": resplit,
    "class_distribution_report": class_distribution,
    "low_cardinality_warning": identity_columns,
    "schema_fingerprint_check": schema_fingerprint,
}


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
    return findings
