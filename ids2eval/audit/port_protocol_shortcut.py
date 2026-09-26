"""Combined port+protocol shortcut check.

identity_column_flag already tests each id_like_columns entry alone, but
destination port and protocol together are a specific, well-known NIDS
shortcut: a handful of (port, protocol) pairs (80/TCP, 443/TCP, 53/UDP,
...) route almost all benign traffic, and attack tools often target one
fixed port, so the pair can separate classes a single column understates,
generalizing across CIC, UNSW, and ToN-IoT-style datasets alike (the same
families where identity_column_flag already flags port alone). This
check quantifies that combined signal specifically, rather than leaving
it as an unmeasured gap between "one column alone" and "the full feature
set."

Needs no new config field: a port-like column is whichever entry in
schema.id_like_columns has "port" in its name (case-insensitive), and a
protocol-like column is whichever loaded column has "proto" in its name
(case-insensitive) - protocol is ordinarily a plain feature, not
id_like, so it is looked for across all columns rather than restricted
to id_like_columns. No-ops if either is missing.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ._auc import robust_auc

AUC_FLAG_THRESHOLD = 0.8


def _find_column(candidates: list[str], needle: str) -> str | None:
    for c in candidates:
        if needle in c.lower():
            return c
    return None


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    id_cols = [c for c in cfg["schema"]["id_like_columns"] if c in train_df.columns]
    port_col = _find_column(id_cols, "port")
    proto_col = _find_column(list(train_df.columns), "proto")

    if not port_col or not proto_col:
        return {
            "check": "port_protocol_shortcut_check", "status": "ok",
            "summary": (
                "no port-like entry in schema.id_like_columns and/or no proto-like "
                "column found, this check needs both"
            ),
            "details": {"port_column": port_col, "protocol_column": proto_col},
        }

    label_col = cfg["schema"]["label_column"]
    cols = [port_col, proto_col]
    categories = {c: pd.Index(train_df[c].astype(str).unique()) for c in cols}
    x_train = pd.DataFrame({c: categories[c].get_indexer(train_df[c].astype(str)) for c in cols})
    x_test = pd.DataFrame({c: categories[c].get_indexer(test_df[c].astype(str)) for c in cols})

    clf = RandomForestClassifier(n_estimators=50, random_state=0, n_jobs=-1)
    clf.fit(x_train, train_df[label_col])
    auc = robust_auc(test_df[label_col], clf.predict_proba(x_test), clf.classes_)

    flagged = auc is not None and auc > AUC_FLAG_THRESHOLD
    status = "flag" if flagged else "ok"
    auc_text = "n/a" if auc is None else f"{auc:.3f}"
    summary = f"standalone AUC of '{port_col}' + '{proto_col}' combined: {auc_text}"
    if flagged:
        summary += ". Port and protocol together may predict the label without attack behavior"

    return {
        "check": "port_protocol_shortcut_check", "status": status, "summary": summary,
        "details": {"port_column": port_col, "protocol_column": proto_col, "standalone_auc": auc},
    }
