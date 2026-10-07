"""Identity-column checks: standalone predictive power + low-cardinality risk.

Per Sarhan et al. 2022 (NetFlow-standard feature set drops IP/port
columns) and Kostas et al. 2024/2025 (packet-level IP/port models hit
near-100% in-dataset, lose >90% cross-dataset): id_like_columns (IP,
port, MAC) are checked both for how well they predict the label alone
(identity_column_flag) and for how few unique values they take relative
to dataset size (low_cardinality_warning generalizes N-BaIoT's
per-device overfitting finding to CIC/UNSW's limited attacker/victim IP
pool).

identity_column_flag asks one specific question: on this split, how well
does looking an identifier value up in the training data predict the
test label? It builds, from the training partition only, a table of how
often each identifier value occurs with each class, and predicts a test
row's class distribution from its value's row of that table (additively
smoothed toward the training class prior). A test value never seen in
training gets the training class prior itself, i.e. no information. The
method uses only equality of values, so it does not depend on any
ordering or integer coding of the identifiers. It is a lookup, not a
model fit, so it uses the whole training partition, not a row sample.

Reported per column: seen_coverage (share of test rows whose value occurs
in training), standalone_auc (weighted one-vs-rest AUC over all test
rows, unseen ones scored with the prior) and seen_only_auc (the same AUC
on the seen rows only). The flag is on standalone_auc, which is the
shortcut's effect on this split as a whole; seen_only_auc shows how
strong the lookup is where it applies. Whether a column is associated
with the label for values never seen in training is a different question,
answered by a split grouped by that column, not by this check.

For a flagged column, details["by_class"] gives the one-vs-rest AUC of the
same lookup for each class of the attack-category (or label) column, so a
global AUC of 0.9 that is actually 0.99 for one attack family and 0.5 for
the rest is visible rather than averaged away.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import _by_class
from ._auc import robust_auc

# Standalone AUC above this on an identity column alone is a specific,
# checkable topology-shortcut signature, not just "IPs are informative."
AUC_FLAG_THRESHOLD = 0.8
# Fewer unique values than this (absolute) suggests the model could be
# memorizing a handful of attacker/victim hosts rather than a behavior.
LOW_CARDINALITY_THRESHOLD = 50
# Past this many classes the per-class breakdown is left out of the report.
MAX_CLASSES_FOR_BREAKDOWN = 25
# Pseudo-count of the additive smoothing toward the training class prior: a
# value seen once in training predicts half its own class, half the prior.
SMOOTHING = 1.0


def _keys(train_col: pd.Series, test_col: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    # Numeric on both sides: compare as float64, exact for integers such as
    # ports. Otherwise compare as strings, so train and test still match on
    # value when one side loaded a column as int and the other as object.
    if pd.api.types.is_numeric_dtype(train_col) and pd.api.types.is_numeric_dtype(test_col):
        return train_col.to_numpy(dtype=float), test_col.to_numpy(dtype=float)
    return train_col.astype(str).to_numpy(), test_col.astype(str).to_numpy()


def lookup_proba(train_keys: np.ndarray, train_y, test_keys: np.ndarray):
    """Class probabilities for each test row from a training-only value table.

    Returns (classes, proba, seen): proba has one column per training class,
    in sorted class order; seen marks test rows whose value occurs in
    training. Unseen rows get the training class prior.
    """
    key_codes, values = pd.factorize(train_keys, use_na_sentinel=False)
    classes = np.asarray(sorted(pd.unique(np.asarray(train_y))))
    y_codes = pd.Index(classes).get_indexer(np.asarray(train_y))
    k = len(classes)
    table = np.bincount(key_codes * k + y_codes, minlength=len(values) * k).reshape(len(values), k).astype(float)
    prior = table.sum(axis=0) / table.sum()
    smoothed = (table + SMOOTHING * prior) / (table.sum(axis=1, keepdims=True) + SMOOTHING)
    idx = pd.Index(values).get_indexer(test_keys)
    seen = idx >= 0
    proba = np.empty((len(idx), k))
    proba[seen] = smoothed[idx[seen]]
    proba[~seen] = prior
    return classes, proba, seen


def check_predictive_power(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    id_cols = [c for c in cfg["schema"]["id_like_columns"] if c in train_df.columns]
    label_col = cfg["schema"]["label_column"]
    if not id_cols:
        return {
            "check": "identity_column_flag", "status": "ok",
            "summary": "no id_like_columns configured", "details": {},
        }

    auc_all, auc_seen, coverage, flagged, keys = {}, {}, {}, [], {}
    y_test = test_df[label_col].to_numpy()
    for col in id_cols:
        train_keys, test_keys = _keys(train_df[col], test_df[col])
        keys[col] = (train_keys, test_keys)
        classes, proba, seen = lookup_proba(train_keys, train_df[label_col], test_keys)
        coverage[col] = float(seen.mean()) if len(seen) else 0.0
        auc_all[col] = robust_auc(y_test, proba, classes)
        auc_seen[col] = robust_auc(y_test[seen], proba[seen], classes) if seen.any() else None
        if auc_all[col] is not None and auc_all[col] > AUC_FLAG_THRESHOLD:
            flagged.append(col)

    def fmt(a):
        return None if a is None else round(a, 3)

    status = "flag" if flagged else "ok"
    summary = "standalone AUC by column (seen-value coverage, AUC on seen values): " + ", ".join(
        f"{c}: {fmt(auc_all[c])} ({coverage[c]:.1%}, {fmt(auc_seen[c])})" for c in id_cols
    )
    if flagged:
        summary += f". Suggest dropping: {flagged}"

    details = {"standalone_auc": auc_all, "seen_only_auc": auc_seen, "seen_coverage": coverage,
               "suggested_drop": flagged, "method": "training-only value lookup, unseen values scored with the prior"}
    if flagged:
        details["by_class"] = {col: _by_class_auc(train_df, test_df, *keys[col], cfg) for col in flagged}

    return {"check": "identity_column_flag", "status": status, "summary": summary, "details": details}


def _by_class_auc(train_df: pd.DataFrame, test_df: pd.DataFrame, train_keys, test_keys, cfg: dict) -> dict | str:
    group_col = _by_class.group_column(cfg)
    classes = _by_class.eligible_classes(train_df, group_col)
    if len(classes) > MAX_CLASSES_FOR_BREAKDOWN:
        return f"skipped, {len(classes)} eligible classes exceeds the {MAX_CLASSES_FOR_BREAKDOWN}-class cap"

    table_classes, proba, _ = lookup_proba(train_keys, train_df[group_col], test_keys)
    position = {c: i for i, c in enumerate(table_classes)}
    y_test = test_df[group_col].to_numpy()
    by_class = {}
    for cls in classes:
        y_binary = y_test == cls
        if not y_binary.any() or y_binary.all():
            continue
        score = proba[:, position[cls]]
        by_class[str(cls)] = robust_auc(y_binary, np.column_stack([1 - score, score]), np.array([False, True]))
    return by_class


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
            f". {flagged} have fewer than {LOW_CARDINALITY_THRESHOLD} unique values, "
            "risk of memorizing specific hosts rather than learning attack behavior"
        )

    return {
        "check": "low_cardinality_warning", "status": status, "summary": summary,
        "details": {"cardinalities": cardinalities, "flagged": flagged},
    }
