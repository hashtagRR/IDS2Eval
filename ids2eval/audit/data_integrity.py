"""Basic dataset sanity checks: missing labels, constant features, ±inf values.

Complements leakage_screen/identity_column_flag (which catch features
that are *too* informative) by catching the opposite class of problem —
features carrying no information at all, or values that will silently
corrupt downstream numeric coercion if left unreported. Structural
problems severe enough to make the dataset unusable (duplicate column
names, a train/test schema that shares no feature columns) are handled
separately in dataset.validate_loaded() as hard failures, not here —
this check only reports things worth a human's attention, not things
that make the rest of the pipeline meaningless.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import features

# A feature with fewer unique values than this (or zero variance for a
# numeric column) is flagged as carrying little-to-no signal.
CONSTANT_NUNIQUE_THRESHOLD = 1


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    label_col = schema["label_column"]
    cols = features.feature_columns(train_df, cfg)

    missing_label = int(train_df[label_col].isna().sum())
    missing_by_feature = {
        c: int(n) for c in cols if (n := train_df[c].isna().sum()) > 0
    }

    inf_by_feature = {}
    constant_features = []
    for c in cols:
        if pd.api.types.is_numeric_dtype(train_df[c]):
            n_inf = int(np.isinf(train_df[c].to_numpy(dtype="float64", na_value=0.0)).sum())
            if n_inf:
                inf_by_feature[c] = n_inf
        if train_df[c].nunique(dropna=True) <= CONSTANT_NUNIQUE_THRESHOLD:
            constant_features.append(c)

    issues = []
    if missing_label:
        issues.append(f"{missing_label} missing label value(s)")
    if missing_by_feature:
        issues.append(f"missing values in {len(missing_by_feature)} feature column(s)")
    if inf_by_feature:
        issues.append(f"+-inf values in {len(inf_by_feature)} feature column(s)")
    if constant_features:
        issues.append(f"{len(constant_features)} constant/near-constant feature(s)")

    status = "flag" if missing_label else ("warning" if issues else "ok")
    summary = "; ".join(issues) if issues else "no missing labels, constant features, or +-inf values found"

    return {
        "check": "data_integrity_check", "status": status, "summary": summary,
        "details": {
            "missing_label_count": missing_label,
            "missing_by_feature": missing_by_feature,
            "inf_by_feature": inf_by_feature,
            "constant_features": constant_features,
        },
    }
