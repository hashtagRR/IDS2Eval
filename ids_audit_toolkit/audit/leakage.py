"""Feature-importance-driven leakage screen (paper Section 3.2).

Fits a fast RandomForest, inspects its own feature_importances_ rather
than guessing candidate leakage columns from domain knowledge, and flags
a single feature or feature pair carrying a large majority of total
split importance — the same method that found real leakage features in
CIC-IDS2018 (Dst Port, Init Win Bytes, FIN Flag Count).
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from .. import features

# A single feature carrying more than this share of total split
# importance is flagged as a specific, checkable shortcut-learning signature.
TOP1_SHARE_THRESHOLD = 0.5
TOP2_SHARE_THRESHOLD = 0.7
MAX_FIT_ROWS = 200_000


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    label_col = cfg["schema"]["label_column"]
    cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=0)
    test_fit = test_df

    x_train, x_test = features.encode_aligned(train_fit, test_fit, cols)
    y_train, y_test = train_fit[label_col], test_fit[label_col]

    clf = RandomForestClassifier(n_estimators=100, random_state=0, n_jobs=-1)
    clf.fit(x_train, y_train)

    importances = pd.Series(clf.feature_importances_, index=cols).sort_values(ascending=False)
    top1_share = float(importances.iloc[0])
    top2_share = float(importances.iloc[:2].sum())

    flagged = top1_share > TOP1_SHARE_THRESHOLD or top2_share > TOP2_SHARE_THRESHOLD
    details = {
        "top_features": importances.head(5).to_dict(),
        "top1_share": top1_share,
        "top2_share": top2_share,
    }

    if flagged:
        top_feature = importances.index[0]
        standalone_auc = _standalone_auc(x_train[[top_feature]], y_train, x_test[[top_feature]], y_test)
        details["standalone_auc"] = {top_feature: standalone_auc}
        summary = (
            f"'{top_feature}' carries {top1_share:.1%} of total split importance "
            f"(standalone AUC={standalone_auc:.3f}) — check whether it's a leakage "
            f"artifact rather than attack-behavior signal"
        )
        status = "flag"
    else:
        summary = f"no single feature or pair dominates importance (top1={top1_share:.1%}, top2={top2_share:.1%})"
        status = "ok"

    return {"check": "leakage_screen", "status": status, "summary": summary, "details": details}


def _standalone_auc(x_train_col, y_train, x_test_col, y_test) -> float:
    clf = RandomForestClassifier(n_estimators=50, random_state=0, n_jobs=-1)
    clf.fit(x_train_col, y_train)
    proba = clf.predict_proba(x_test_col)
    if proba.shape[1] == 2:
        return float(roc_auc_score(y_test, proba[:, 1]))
    return float(roc_auc_score(y_test, proba, multi_class="ovr", average="weighted"))
