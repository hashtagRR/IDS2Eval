"""Timestamp-only leakage check.

Per Wu & Keogh 2021's "run-to-failure bias" (IEEE TKDE, time-series
anomaly detection): several widely-used benchmarks were collected such
that anomalies cluster near the end of the recording, so a model can win
by learning "predict positive late" rather than the anomaly itself. NIDS
datasets built as a sequence of scenario-specific time windows (attack X
launched 2-3pm, attack Y launched 3-4pm, ...) have the same structure -
independently confirmed against this project's own real CIC-IDS2018 run,
where a RandomForest given nothing but the Timestamp column reached
AUC 0.93 predicting benign vs. attack. Same method as identity_column_flag
(a standalone classifier on one column), scoped to whichever column
schema.timestamp_column names, since there's no universal column name to
detect automatically the way id_like_columns are user-declared too.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ._auc import robust_auc
from ._time import to_numeric_time

AUC_FLAG_THRESHOLD = 0.8
MAX_FIT_ROWS = 200_000


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    col = cfg["schema"]["timestamp_column"]
    label_col = cfg["schema"]["label_column"]
    if not col or col not in train_df.columns:
        return {
            "check": "temporal_leakage_check", "status": "ok",
            "summary": "no schema.timestamp_column configured", "details": {},
        }

    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=0)
    x_train = to_numeric_time(train_fit[col]).fillna(0).to_numpy().reshape(-1, 1)
    x_test = to_numeric_time(test_df[col]).fillna(0).to_numpy().reshape(-1, 1)
    y_train, y_test = train_fit[label_col], test_df[label_col]

    clf = RandomForestClassifier(n_estimators=50, random_state=0, n_jobs=-1)
    clf.fit(x_train, y_train)
    auc = robust_auc(y_test, clf.predict_proba(x_test), clf.classes_)

    flagged = auc is not None and auc > AUC_FLAG_THRESHOLD
    status = "flag" if flagged else "ok"
    auc_text = "n/a" if auc is None else f"{auc:.3f}"
    summary = f"standalone AUC of '{col}' alone: {auc_text}"
    if flagged:
        summary += ". Timestamp alone may predict the label without learning attack behavior"

    return {
        "check": "temporal_leakage_check", "status": status, "summary": summary,
        "details": {"column": col, "standalone_auc": auc},
    }
