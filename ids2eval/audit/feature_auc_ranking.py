"""All-feature standalone AUC ranking.

identity_column_flag, port_protocol_shortcut_check, and
temporal_leakage_check each test one declared column (or pair) for
standalone predictive power, via a model fit, since a small classifier
is needed to turn an arbitrary categorical column into a score. This
check ranks every NUMERIC feature the same way, but without fitting
anything: a numeric column's own raw values already are a score, so
its one-vs-rest AUC against each class is a direct roc_auc_score call.
Categorical columns are not covered here (their category codes carry
no meaningful order, unlike a numeric value), the model-based checks
already cover those.

Deliberately a higher flag threshold than identity_column_flag's 0.8:
this ranks every behavioral feature too, ones expected to correlate
with the label to some degree on their own, so only a near-perfect
single feature is a specific, checkable oddity worth a flag.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from ..data import features

AUC_FLAG_THRESHOLD = 0.95
AUC_WARNING_THRESHOLD = 0.90
TOP_N = 5


def _best_auc(values, labels: pd.Series):
    """The best one-vs-rest AUC this column reaches against any single
    class, and which class, or None if no class has both members present.

    Each class's AUC is the Mann-Whitney statistic from one ranking of the
    column (average ranks for ties, which is how ROC AUC scores ties), so
    the column is sorted once rather than once per class: equal to
    roc_auc_score's value, at a fraction of the cost on tens of millions of
    rows. A column holding +-inf is skipped, as roc_auc_score rejects it.
    """
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        return None, None
    classes, codes = np.unique(labels.to_numpy(), return_inverse=True)
    n = len(values)
    n_pos = np.bincount(codes, minlength=len(classes)).astype(float)
    rank_sum = np.bincount(codes, weights=rankdata(values), minlength=len(classes))
    auc_by_class = {}
    for i, cls in enumerate(classes):
        if n_pos[i] == 0 or n_pos[i] == n:
            continue
        auc = (rank_sum[i] - n_pos[i] * (n_pos[i] + 1) / 2) / (n_pos[i] * (n - n_pos[i]))
        # A feature can separate a class by high values or low values;
        # max() with the inverse reports separability regardless of direction.
        auc_by_class[cls] = max(auc, 1 - auc)
    best_auc, best_class = None, None
    for cls in labels.unique():  # same tie-break order as before: first class to reach the maximum
        auc = auc_by_class.get(cls)
        if auc is not None and (best_auc is None or auc > best_auc):
            best_auc, best_class = float(auc), cls
    return best_auc, best_class


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    label_col = cfg["schema"]["label_column"]
    cols = features.feature_columns(train_df, cfg)
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(train_df[c])]
    if not numeric_cols:
        return {
            "check": "feature_auc_ranking_check", "status": "ok",
            "summary": "no numeric feature columns to rank", "details": {},
        }

    labels = train_df[label_col]

    def score(col):
        values = train_df[col].to_numpy()
        valid = ~pd.isna(values)
        if valid.sum() < 2:
            return None, None
        return _best_auc(values[valid], labels[valid])

    # Columns are ranked in threads: numpy's sort releases the GIL, and at
    # full scale ranking dozens of columns of tens of millions of rows one by
    # one dominates the audit's run time.
    with ThreadPoolExecutor(max_workers=min(len(numeric_cols), os.cpu_count() or 1, 16)) as pool:
        scored = list(pool.map(score, numeric_cols))

    best_per_feature = {}
    top_feature, top_class, top_auc = None, None, 0.0
    for col, (auc, cls) in zip(numeric_cols, scored, strict=True):
        if auc is None:
            continue
        best_per_feature[col] = auc
        if auc > top_auc:
            top_feature, top_class, top_auc = col, cls, auc

    if not best_per_feature:
        return {
            "check": "feature_auc_ranking_check", "status": "ok",
            "summary": "no numeric feature had both classes present to rank", "details": {},
        }

    if top_auc > AUC_FLAG_THRESHOLD:
        status = "flag"
    elif top_auc > AUC_WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "ok"

    top_ranked = dict(sorted(best_per_feature.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N])
    summary = f"'{top_feature}' alone reaches AUC {top_auc:.3f} identifying '{top_class}'"
    if status != "ok":
        summary += "; a single feature this separable is worth checking for a leakage artifact"

    return {
        "check": "feature_auc_ranking_check", "status": status, "summary": summary,
        "details": {"top_features": top_ranked, "best_feature": str(top_feature), "best_class": str(top_class)},
    }
