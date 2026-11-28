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

A raw-value AUC sees only features whose values rank the classes. A feature
that marks an attack class by one specific value (a fixed byte count from an
attack tool, say) sits in the middle of the benign range and escapes it. Since
version 0.3.1 the check therefore also computes a value-lookup statistic: for
each numeric feature and each class with at least MIN_CLASS_SIZE training rows,
a one-feature lookup learns, on one half of the training rows, which values
mark the class rather than the reference (benign) class, and its F1 is scored
on the other half. The lookup is held out, so a value that occurs once cannot
score, and it needs no model. Each class is compared with the reference class
alone, as a single-feature test of a class against benign traffic would. The
status is the more severe of the two statistics' tiers, which are the same
(0.95 flag, 0.90 warning).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from ..data import features
from ._by_class import MIN_CLASS_SIZE, group_column
from ._status import NOT_APPLICABLE

AUC_FLAG_THRESHOLD = 0.95
AUC_WARNING_THRESHOLD = 0.90
TOP_N = 5
# value lookup: rows per class kept (at random) so the statistic stays bounded on
# corpora of tens of millions of rows, and names that mark the reference class
VALUE_RULE_ROWS_PER_CLASS = 100_000
BENIGN_NAMES = {"benign", "normal"}


def _reference_class(labels: pd.Series, cfg: dict):
    """The class every other class is compared with: schema.benign_label if set,
    else the one class named benign or normal, else the training majority class."""
    present = list(pd.unique(labels))
    configured = cfg["schema"].get("benign_label")
    if configured is not None:
        hits = [c for c in present if str(c) == str(configured)]
        return (hits[0], "schema.benign_label") if hits else (None, "schema.benign_label not found in training labels")
    named = [c for c in present if str(c).strip().lower() in BENIGN_NAMES]
    if len(named) == 1:
        return named[0], "class named " + str(named[0])
    return labels.value_counts().index[0], "training majority class"


def _value_rule_f1(values: np.ndarray, codes: np.ndarray, ref: int, half: np.ndarray, n_classes: int) -> np.ndarray:
    """Held-out F1, per class, of the one-feature lookup "value v marks class c".

    On the first half, v marks c when c's rows with value v outnumber the
    reference class's (ties go to the reference). On the second half each class
    is scored against the reference class only: TP, rows of c whose value marks
    c; FP, reference rows whose value marks c; FN, rows of c whose value does
    not. Values unseen in the first half mark nothing. Returns NaN for the
    reference class and for classes absent from either half.
    """
    _, v = np.unique(values, return_inverse=True)
    n_values = int(v.max()) + 1
    a, b = half, ~half
    joint_a, counts_a = np.unique(v[a].astype(np.int64) * n_classes + codes[a], return_counts=True)
    va, ca = joint_a // n_classes, joint_a % n_classes
    ref_a = np.zeros(n_values)
    ref_a[va[ca == ref]] = counts_a[ca == ref]
    marks = (ca != ref) & (counts_a > ref_a[va])
    mark_codes = joint_a[marks]
    ref_b = np.bincount(v[b & (codes == ref)], minlength=n_values)
    fp = np.bincount(ca[marks], weights=ref_b[va[marks]], minlength=n_classes)
    tp = np.bincount(codes[b], weights=np.isin(v[b].astype(np.int64) * n_classes + codes[b], mark_codes),
                     minlength=n_classes)
    n_b = np.bincount(codes[b], minlength=n_classes).astype(float)
    n_a = np.bincount(codes[a], minlength=n_classes)
    with np.errstate(invalid="ignore", divide="ignore"):
        f1 = 2 * tp / (tp + fp + n_b)
    f1[(n_a == 0) | (n_b == 0)] = np.nan
    f1[ref] = np.nan
    return f1


def _value_rules(train_df: pd.DataFrame, numeric_cols: list, cfg: dict) -> dict:
    """Best held-out value-lookup F1 for each eligible class, with its feature."""
    groups = train_df[group_column(cfg)]
    ref, ref_source = _reference_class(groups, cfg)
    if ref is None:
        return {"reference_class": None, "reference_source": ref_source, "by_class": {}}
    counts = groups.value_counts()
    eligible = [c for c in counts.index if counts[c] >= MIN_CLASS_SIZE and c != ref]
    if not eligible:
        return {"reference_class": str(ref), "reference_source": ref_source, "by_class": {}}
    rng = np.random.default_rng(cfg["random_seed"])
    # every reference and eligible row up to the per-class cap, then a random half split
    keep = []
    for c in [ref, *eligible]:
        idx = np.flatnonzero((groups == c).to_numpy())
        if len(idx) > VALUE_RULE_ROWS_PER_CLASS:
            idx = rng.choice(idx, VALUE_RULE_ROWS_PER_CLASS, replace=False)
        keep.append(idx)
    keep = np.sort(np.concatenate(keep))
    sub_groups = groups.to_numpy()[keep]
    classes = [ref, *eligible]
    code_of = {c: i for i, c in enumerate(classes)}
    codes = pd.Series(sub_groups).map(code_of).to_numpy(dtype=np.int64)
    half = rng.random(len(keep)) < 0.5

    def score(col):
        values = train_df[col].to_numpy()[keep]
        valid = ~pd.isna(values)
        if valid.sum() < 2:
            return None
        return _value_rule_f1(np.asarray(values[valid], dtype=float), codes[valid], 0, half[valid], len(classes))

    with ThreadPoolExecutor(max_workers=min(len(numeric_cols), os.cpu_count() or 1, 8)) as pool:
        scored = list(pool.map(score, numeric_cols))
    by_class = {}
    for col, f1 in zip(numeric_cols, scored, strict=True):
        if f1 is None:
            continue
        for i, c in enumerate(classes[1:], start=1):
            if not np.isnan(f1[i]) and (str(c) not in by_class or f1[i] > by_class[str(c)]["f1"]):
                by_class[str(c)] = {"feature": str(col), "f1": float(f1[i])}
    return {"reference_class": str(ref), "reference_source": ref_source, "by_class": by_class}


def _tier(value: float) -> str:
    if value > AUC_FLAG_THRESHOLD:
        return "flag"
    if value > AUC_WARNING_THRESHOLD:
        return "warning"
    return "ok"


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
            "check": "feature_auc_ranking_check", "status": NOT_APPLICABLE,
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
            "check": "feature_auc_ranking_check", "status": NOT_APPLICABLE,
            "summary": "no numeric feature had both classes present to rank", "details": {},
        }

    value_rules = _value_rules(train_df, numeric_cols, cfg)
    best_rule = max(value_rules["by_class"].items(), key=lambda kv: kv[1]["f1"], default=None)
    order = {"ok": 0, "warning": 1, "flag": 2}
    auc_status = _tier(top_auc)
    rule_status = _tier(best_rule[1]["f1"]) if best_rule else "ok"
    status = max(auc_status, rule_status, key=order.get)

    top_ranked = dict(sorted(best_per_feature.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N])
    summary = f"'{top_feature}' alone reaches AUC {top_auc:.3f} identifying '{top_class}'"
    if best_rule:
        cls, rule = best_rule
        summary += (f"; values of '{rule['feature']}' alone mark '{cls}' against "
                    f"'{value_rules['reference_class']}' with held-out F1 {rule['f1']:.3f}")
    if status != "ok":
        summary += "; a single feature this separable is worth checking for a leakage artifact"

    return {
        "check": "feature_auc_ranking_check", "status": status, "summary": summary,
        "details": {"top_features": top_ranked, "best_feature": str(top_feature), "best_class": str(top_class),
                    "auc_status": auc_status, "value_rule_status": rule_status, "value_rules": value_rules},
    }
