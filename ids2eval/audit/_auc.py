"""ROC AUC that survives a class-set mismatch between train and test.

Shared by the checks that score a single-column classifier (leakage_screen's
standalone AUC, identity_column_flag). A plain roc_auc_score call assumes the
model's classes and the test labels are the same set, which real splits
break both ways: a rare class can land entirely in train (CIC-IDS2018's
SQL Injection, ~3 rows in a 500K reservoir sample - a real crash), and a
dataset can hold test-only classes by design (NSL-KDD's novel attacks).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

logger = logging.getLogger(__name__)


def robust_auc(y_true, proba: np.ndarray, classes) -> float | None:
    """Weighted one-vs-rest AUC over the classes present on both sides.

    Test rows whose class the model never saw are skipped (there's no
    score column to rank them by); probability columns for classes absent
    from the test labels are dropped and each row renormalized. Returns
    None when fewer than two classes remain - AUC isn't defined there.
    With identical class sets this equals plain roc_auc_score.
    """
    y_true = pd.Series(y_true).to_numpy()
    classes = np.asarray(classes)

    seen = np.isin(y_true, classes)
    if not seen.all():
        logger.warning("AUC: skipped %d test row(s) whose class never appeared in train", int((~seen).sum()))
    y_true, proba = y_true[seen], proba[seen]

    present = np.isin(classes, np.unique(y_true))
    if present.sum() < 2:
        return None
    classes, proba = classes[present], proba[:, present]

    row_sums = proba.sum(axis=1, keepdims=True)
    proba = np.divide(proba, row_sums, out=np.full_like(proba, 1.0 / len(classes)), where=row_sums > 0)
    if len(classes) == 2:
        return float(roc_auc_score(y_true == classes[1], proba[:, 1]))
    return float(roc_auc_score(y_true, proba, multi_class="ovr", average="weighted", labels=classes))
