"""Reuse-removal falsification (opt-in).

dedup_check counts test rows whose feature vector also occurs in training,
and comparing those rows' scores with the other test rows' is observational:
reused rows come from different classes and conditions than novel ones, so
even a class-adjusted difference does not show that training exposure caused
it. This check intervenes instead. It removes every training row whose
feature vector matches some test row, refits the reference model, and scores
the same, unchanged test set. Removing training rows also shrinks and
reshapes the training set, so the comparison is against removing the same
number of randomly chosen training rows with the same class mix: the
difference between the two refits is the effect of training on exactly the
reused vectors, with training size and class support held fixed.

Repeated over audit.repeated_seed_count seeds (each seed redraws the random
removal and reseeds the model); each metric gets a mean difference, a 95%
Student-t interval and the three-way verdict of
repeated_seed_falsification_check. A positive difference means the model
scores higher on this test set because it saw the reused vectors in
training. The score on the reused test rows alone is reported too, since
that is where an effect would concentrate.

Works on the split it is given, so it must see the data before
preprocessing.dedup removes the reused rows; after deduplication no test
row matches training and the check reports not_applicable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import _metrics
from ._fit_score import fit_and_predict
from ._status import NOT_APPLICABLE
from .resplit import MATERIAL_DROP_THRESHOLD

_CHECK_NAME = "reuse_removal_falsification"
MIN_SEEDS = 3


def _keys(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return pd.util.hash_pandas_object(df[cols], index=False).to_numpy()


def _interval(values: list[float]) -> tuple[float, float, float]:
    centre = float(np.mean(values))
    half = stats.t.ppf(0.975, df=len(values) - 1) * float(np.std(values, ddof=1)) / len(values) ** 0.5
    return centre, centre - half, centre + half


def _matched_class_mix_sample(train_df: pd.DataFrame, removed: pd.DataFrame, label_col: str,
                              rng: np.random.Generator) -> np.ndarray:
    """Positions of randomly chosen training rows with the same per-class counts
    as the removed rows."""
    chosen = []
    for label, count in removed[label_col].value_counts().items():
        pool = np.flatnonzero((train_df[label_col] == label).to_numpy())
        chosen.append(rng.choice(pool, size=count, replace=False))
    return np.concatenate(chosen)


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    schema = cfg["schema"]
    label_col = schema["label_column"]
    ignore = set(schema["drop_columns"]) | {label_col}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    compare_cols = [c for c in train_df.columns if c not in ignore]

    n_seeds = cfg["audit"]["repeated_seed_count"]
    if n_seeds < MIN_SEEDS:
        return {
            "check": _CHECK_NAME, "status": NOT_APPLICABLE,
            "summary": f"audit.repeated_seed_count ({n_seeds}) is below the minimum of {MIN_SEEDS}",
            "details": {},
        }

    test_keys = _keys(test_df, compare_cols)
    train_keys = _keys(train_df, compare_cols)
    matched_train = np.isin(train_keys, test_keys)
    reused_test = np.isin(test_keys, train_keys)
    n_removed = int(matched_train.sum())
    if n_removed == 0:
        return {
            "check": _CHECK_NAME, "status": NOT_APPLICABLE,
            "summary": "no training row shares a feature vector with a test row, nothing to remove",
            "details": {"training_rows_removed": 0},
        }
    kept = train_df[~matched_train]
    if kept[label_col].nunique() < 2:
        return {
            "check": _CHECK_NAME, "status": NOT_APPLICABLE,
            "summary": "removing the matching training rows leaves fewer than two classes",
            "details": {"training_rows_removed": n_removed},
        }

    y_test = test_df[label_col].to_numpy()
    removed = train_df[matched_train]
    per_seed = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        control_positions = _matched_class_mix_sample(train_df, removed, label_col, rng)
        control = train_df.drop(train_df.index[control_positions])
        pred_reuse_removed = fit_and_predict(kept, test_df, label_col, cfg, seed=seed)
        pred_control = fit_and_predict(control, test_df, label_col, cfg, seed=seed)
        full_control = _metrics.scores_from_predictions(y_test, pred_control).metrics
        full_removed = _metrics.scores_from_predictions(y_test, pred_reuse_removed).metrics
        reused_control = _metrics.scores_from_predictions(y_test[reused_test], pred_control[reused_test]).metrics
        reused_removed = _metrics.scores_from_predictions(
            y_test[reused_test], pred_reuse_removed[reused_test]
        ).metrics
        per_seed.append({
            "full_test": {m: full_control[m] - full_removed[m] for m in _metrics.METRICS},
            "reused_test_rows": {m: reused_control[m] - reused_removed[m] for m in _metrics.METRICS},
            "control_accuracy": full_control["accuracy"],
            "reuse_removed_accuracy": full_removed["accuracy"],
        })

    thresholds = _metrics.thresholds(cfg, _CHECK_NAME, MATERIAL_DROP_THRESHOLD)
    by_metric, verdicts = {}, {}
    for m in _metrics.METRICS:
        diffs = [s["full_test"][m] for s in per_seed]
        centre, low, high = _interval(diffs)
        verdicts[m] = _metrics.interval_verdict(low, high, thresholds[m])
        reused_centre, reused_low, reused_high = _interval([s["reused_test_rows"][m] for s in per_seed])
        by_metric[m] = {
            "differences_by_seed": diffs, "mean_difference": centre, "ci_95": [low, high],
            "threshold": thresholds[m], "verdict": verdicts[m],
            "reused_rows_mean_difference": reused_centre,
            "reused_rows_ci_95": [reused_low, reused_high],
        }
    status = _metrics.combined_status(verdicts, cfg)

    acc = by_metric["accuracy"]
    summary = (
        f"removing the {n_removed:,} training rows that share a feature vector with a test row, against "
        f"removing as many random rows of the same classes, over {n_seeds} seeds: score difference "
        f"on the unchanged test set, mean [95% CI], accuracy {acc['mean_difference']:+.4f} "
        f"[{acc['ci_95'][0]:+.4f}, {acc['ci_95'][1]:+.4f}], balanced accuracy "
        f"{by_metric['balanced_accuracy']['mean_difference']:+.4f}, macro-F1 "
        f"{by_metric['macro_f1']['mean_difference']:+.4f} ({_metrics.describe(verdicts)}); on the "
        f"{int(reused_test.sum()):,} reused test rows alone, accuracy {acc['reused_rows_mean_difference']:+.4f}"
    )
    return {
        "check": _CHECK_NAME, "status": status, "summary": summary,
        "details": {
            "training_rows_removed": n_removed, "training_rows": len(train_df),
            "reused_test_rows": int(reused_test.sum()), "test_rows": len(test_df),
            "n_seeds": n_seeds, "by_metric": by_metric, "per_seed": per_seed,
            "materiality_metrics": list(cfg["audit"]["materiality_metrics"]),
        },
    }
