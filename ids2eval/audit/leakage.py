"""Feature-importance-driven leakage screen (paper Section 3.2).

Fits a fast RandomForest, inspects its own feature_importances_ rather
than guessing candidate leakage columns from domain knowledge, and flags
a single feature or feature pair carrying a large majority of total
split importance. Same method that found real leakage features in
CIC-IDS2018 (Dst Port, Init Win Bytes, FIN Flag Count).

When flagged, also attaches a per-class breakdown (details["by_class"]):
one-vs-rest AUC of the flagged feature's raw values against each class,
via roc_auc_score directly rather than fitting one classifier per class -
a numeric feature's own values already are the score, no model needed.
A class where the feature separates as well as the global fit and one
where it doesn't tells a different story than the aggregate hides.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from ..data import features
from . import _by_class
from ._auc import robust_auc

# A single feature carrying more than this share of total split
# importance is flagged as a specific, checkable shortcut-learning signature.
TOP1_SHARE_THRESHOLD = 0.5
TOP2_SHARE_THRESHOLD = 0.7
MAX_FIT_ROWS = 200_000


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict, seed: int = 0) -> dict:
    """seed only varies the sample draw and the classifier's own randomness -
    used by seed_sensitivity_check to test whether the flag/ok conclusion
    holds up across seeds, not by the default single-seed run.
    """
    label_col = cfg["schema"]["label_column"]
    cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    test_fit = test_df

    x_train, x_test = features.encode_aligned(train_fit, test_fit, cols)
    y_train, y_test = train_fit[label_col], test_fit[label_col]

    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)
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
        standalone_auc = _standalone_auc(x_train[[top_feature]], y_train, x_test[[top_feature]], y_test, seed)
        details["standalone_auc"] = {top_feature: standalone_auc}
        details["by_class"] = _by_class_auc(train_fit, x_train[top_feature].to_numpy(), cfg)
        auc_text = "n/a" if standalone_auc is None else f"{standalone_auc:.3f}"
        summary = (
            f"'{top_feature}' carries {top1_share:.1%} of total split importance "
            f"(standalone AUC={auc_text}). Check whether it's a leakage "
            f"artifact rather than attack-behavior signal"
        )
        status = "flag"
    else:
        summary = f"no single feature or pair dominates importance (top1={top1_share:.1%}, top2={top2_share:.1%})"
        status = "ok"

    return {"check": "leakage_screen", "status": status, "summary": summary, "details": details}


def _standalone_auc(x_train_col, y_train, x_test_col, y_test, seed: int = 0) -> float | None:
    clf = RandomForestClassifier(n_estimators=50, random_state=seed, n_jobs=-1)
    clf.fit(x_train_col, y_train)
    return robust_auc(y_test, clf.predict_proba(x_test_col), clf.classes_)


def _by_class_auc(train_fit: pd.DataFrame, feature_values, cfg: dict) -> dict:
    group_col = _by_class.group_column(cfg)
    by_class = {}
    for cls in _by_class.eligible_classes(train_fit, group_col):
        y_binary = (train_fit[group_col] == cls).to_numpy()
        if not y_binary.any() or y_binary.all():
            continue
        auc = roc_auc_score(y_binary, feature_values)
        # A feature can separate a class either by high values or low values -
        # max() with the inverse reports separability regardless of direction,
        # same convention as a rule-based threshold could use either side.
        by_class[str(cls)] = float(max(auc, 1 - auc))
    return by_class
