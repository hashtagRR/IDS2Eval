"""Identity-column checks: standalone predictive power + low-cardinality risk.

Per Sarhan et al. 2022 (NetFlow-standard feature set drops IP/port
columns) and Kostas et al. 2024/2025 (packet-level IP/port models hit
near-100% in-dataset, lose >90% cross-dataset): id_like_columns (IP,
port, MAC) are checked both for how well they predict the label alone
(identity_column_flag) and for how few unique values they take relative
to dataset size (low_cardinality_warning generalizes N-BaIoT's
per-device overfitting finding to CIC/UNSW's limited attacker/victim IP
pool).

For a flagged column, identity_column_flag also attaches a per-class
breakdown (details["by_class"]): one-vs-rest AUC of that column alone
against each class, so a global AUC of 0.9 that is actually 0.99 for one
attack family and 0.5 for the rest is visible rather than averaged away.
Capped at MAX_CLASSES_FOR_BREAKDOWN classes, since each one is a real
extra model fit, unlike leakage_screen's per-class breakdown which reuses
raw feature values and needs no fit at all.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from . import _by_class
from ._auc import robust_auc

# Standalone AUC above this on an identity column alone is a specific,
# checkable topology-shortcut signature, not just "IPs are informative."
AUC_FLAG_THRESHOLD = 0.8
# Fewer unique values than this (absolute) suggests the model could be
# memorizing a handful of attacker/victim hosts rather than a behavior.
LOW_CARDINALITY_THRESHOLD = 50
# A per-class breakdown fits one small classifier per eligible class; past
# this many classes the extra compute stops being a cheap add-on.
MAX_CLASSES_FOR_BREAKDOWN = 25


def check_predictive_power(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    id_cols = [c for c in cfg["schema"]["id_like_columns"] if c in train_df.columns]
    label_col = cfg["schema"]["label_column"]
    if not id_cols:
        return {
            "check": "identity_column_flag", "status": "ok",
            "summary": "no id_like_columns configured", "details": {},
        }

    results = {}
    flagged = []
    encoded_columns = {}
    for col in id_cols:
        categories = pd.Index(train_df[col].astype(str).unique())
        x_train = categories.get_indexer(train_df[col].astype(str)).reshape(-1, 1)
        x_test = categories.get_indexer(test_df[col].astype(str)).reshape(-1, 1)
        encoded_columns[col] = (x_train, x_test)

        clf = RandomForestClassifier(n_estimators=50, random_state=0, n_jobs=-1)
        clf.fit(x_train, train_df[label_col])
        auc = robust_auc(test_df[label_col], clf.predict_proba(x_test), clf.classes_)
        results[col] = auc
        if auc is not None and auc > AUC_FLAG_THRESHOLD:
            flagged.append(col)

    status = "flag" if flagged else "ok"
    summary = f"standalone AUC by column: { {c: None if a is None else round(a, 3) for c, a in results.items()} }"
    if flagged:
        summary += f". Suggest dropping: {flagged}"

    details = {"standalone_auc": results, "suggested_drop": flagged}
    if flagged:
        details["by_class"] = {
            col: _by_class_auc(train_df, test_df, *encoded_columns[col], cfg) for col in flagged
        }

    return {"check": "identity_column_flag", "status": status, "summary": summary, "details": details}


def _by_class_auc(
    train_df: pd.DataFrame, test_df: pd.DataFrame, x_train_col, x_test_col, cfg: dict
) -> dict | str:
    group_col = _by_class.group_column(cfg)
    classes = _by_class.eligible_classes(train_df, group_col)
    if len(classes) > MAX_CLASSES_FOR_BREAKDOWN:
        return f"skipped, {len(classes)} eligible classes exceeds the {MAX_CLASSES_FOR_BREAKDOWN}-class cap"

    by_class = {}
    for cls in classes:
        y_train_binary = (train_df[group_col] == cls).to_numpy()
        y_test_binary = (test_df[group_col] == cls).to_numpy()
        if not y_train_binary.any() or y_train_binary.all() or not y_test_binary.any():
            continue
        clf = RandomForestClassifier(n_estimators=50, random_state=0, n_jobs=-1)
        clf.fit(x_train_col, y_train_binary)
        auc = robust_auc(y_test_binary, clf.predict_proba(x_test_col), clf.classes_)
        by_class[str(cls)] = auc
    return by_class


def check_cardinality(train_df: pd.DataFrame, cfg: dict) -> dict:
    id_cols = [c for c in cfg["schema"]["id_like_columns"] if c in train_df.columns]
    if not id_cols:
        return {
            "check": "low_cardinality_warning", "status": "ok",
            "summary": "no id_like_columns configured", "details": {},
        }

    cardinalities = {c: int(train_df[c].nunique()) for c in id_cols}
    flagged = [c for c, n in cardinalities.items() if n < LOW_CARDINALITY_THRESHOLD]

    status = "warning" if flagged else "ok"
    summary = f"unique values by column: {cardinalities}"
    if flagged:
        summary += (
            f". {flagged} have fewer than {LOW_CARDINALITY_THRESHOLD} unique values, "
            "risk of memorizing specific hosts rather than learning attack behavior"
        )

    return {
        "check": "low_cardinality_warning", "status": status, "summary": summary,
        "details": {"cardinalities": cardinalities, "flagged": flagged},
    }
