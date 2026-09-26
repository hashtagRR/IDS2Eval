"""Counterfactual artifact-sensitivity test (v2, opt-in).

Fits one RandomForest on every feature and predicts on test, then, for
each column already declared as a potential shortcut elsewhere
(schema.id_like_columns, schema.timestamp_column), permutes just that
column's own values across the test rows (a real, in-distribution
reshuffle, not a synthetic replacement) and predicts again with the
same already-fitted model. The share of predictions that flip is a
direct measurement of how much the model's decision for a given row
depends on that one column rather than the rest of the row's features:

    AS(column) = P(model's prediction changes | only this column reshuffled)

High sensitivity to an identity or timestamp column specifically is a
concrete, checkable sign the model may be keying off which host or
which moment produced a flow rather than what the flow's behavior was,
complementing identity_column_flag/temporal_leakage_check's standalone
predictive-power tests with the model's actual dependence on the
column inside the full feature set, not the column in isolation.

Deliberately opt-in: which classifier is fit and how a specific column
is perturbed both shape the result, unlike a check that measures a
fixed statistic of the data itself. No-ops unless at least one
declared identity or timestamp column is actually present as a feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ..data import features

MAX_FIT_ROWS = 200_000
FLIP_RATE_FLAG_THRESHOLD = 0.30
FLIP_RATE_WARNING_THRESHOLD = 0.15


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    candidate_cols = list(schema["id_like_columns"])
    if schema["timestamp_column"]:
        candidate_cols.append(schema["timestamp_column"])

    cols = features.feature_columns(train_df, cfg)
    suspicious_cols = [c for c in dict.fromkeys(candidate_cols) if c in cols and c in test_df.columns]
    if not suspicious_cols:
        return {
            "check": "artifact_sensitivity_check", "status": "ok",
            "summary": "no schema.id_like_columns or schema.timestamp_column present as a feature",
            "details": {},
        }

    label_col = schema["label_column"]
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=0)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols)
    clf = RandomForestClassifier(n_estimators=100, random_state=0, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])
    baseline_pred = clf.predict(x_test)

    rng = np.random.RandomState(0)
    flip_rate_by_column = {}
    for col in suspicious_cols:
        perturbed_test = test_df.copy()
        perturbed_test[col] = rng.permutation(perturbed_test[col].to_numpy())
        _, x_test_perturbed = features.encode_aligned(train_fit, perturbed_test, cols)
        perturbed_pred = clf.predict(x_test_perturbed)
        flip_rate_by_column[col] = float((perturbed_pred != baseline_pred).mean())

    worst_col, worst_rate = max(flip_rate_by_column.items(), key=lambda kv: kv[1])
    if worst_rate > FLIP_RATE_FLAG_THRESHOLD:
        status = "flag"
    elif worst_rate > FLIP_RATE_WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "ok"

    summary = f"reshuffling '{worst_col}' alone flips {worst_rate:.1%} of the model's predictions"
    if status != "ok":
        summary += "; the model's decisions depend on this column more than its own behavior may warrant"

    return {
        "check": "artifact_sensitivity_check", "status": status, "summary": summary,
        "details": {"flip_rate_by_column": flip_rate_by_column},
    }
