"""Identity-column checks: standalone predictive power + low-cardinality risk.

Per Sarhan et al. 2022 (NetFlow-standard feature set drops IP/port
columns) and Kostas et al. 2024/2025 (packet-level IP/port models hit
near-100% in-dataset, lose >90% cross-dataset): id_like_columns (IP,
port, MAC) are checked both for how well they predict the label alone
(identity_column_flag) and for how few unique values they take relative
to dataset size (low_cardinality_warning — generalizes N-BaIoT's
per-device overfitting finding to CIC/UNSW's limited attacker/victim IP
pool).
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

# Standalone AUC above this on an identity column alone is a specific,
# checkable topology-shortcut signature, not just "IPs are informative."
AUC_FLAG_THRESHOLD = 0.8
# Fewer unique values than this (absolute) suggests the model could be
# memorizing a handful of attacker/victim hosts rather than a behavior.
LOW_CARDINALITY_THRESHOLD = 50


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
    for col in id_cols:
        categories = pd.Index(train_df[col].astype(str).unique())
        x_train = categories.get_indexer(train_df[col].astype(str)).reshape(-1, 1)
        x_test = categories.get_indexer(test_df[col].astype(str)).reshape(-1, 1)

        clf = RandomForestClassifier(n_estimators=50, random_state=0, n_jobs=-1)
        clf.fit(x_train, train_df[label_col])
        proba = clf.predict_proba(x_test)
        auc = float(roc_auc_score(test_df[label_col], proba[:, 1])) if proba.shape[1] == 2 \
            else float(roc_auc_score(test_df[label_col], proba, multi_class="ovr", average="weighted"))
        results[col] = auc
        if auc > AUC_FLAG_THRESHOLD:
            flagged.append(col)

    status = "flag" if flagged else "ok"
    summary = f"standalone AUC by column: { {c: round(a, 3) for c, a in results.items()} }"
    if flagged:
        summary += f" — suggest dropping: {flagged}"

    return {
        "check": "identity_column_flag", "status": status, "summary": summary,
        "details": {"standalone_auc": results, "suggested_drop": flagged},
    }


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
            f" — {flagged} have fewer than {LOW_CARDINALITY_THRESHOLD} unique values, "
            "risk of memorizing specific hosts rather than learning attack behavior"
        )

    return {
        "check": "low_cardinality_warning", "status": status, "summary": summary,
        "details": {"cardinalities": cardinalities, "flagged": flagged},
    }
