"""Resplit falsification test (paper Section 3.5).

The nearest-neighbor test alone can't distinguish "this class is
inherently homogeneous" from "a different split would reveal real
difficulty that random sampling happens to hide", both hypotheses look
identical under random sampling. Constructing a non-random split along a
dimension the random split ignores (session/group identity) and
observing whether the score changes breaks that symmetry: if
session-correlated leakage across the random split's boundary had been
doing real work, the grouped split should cost measurable performance.

Scores accuracy, balanced accuracy and macro-F1 and gives each its own
verdict (see _metrics); the status is the most severe verdict among
audit.materiality_metrics. Reports the grouping key's group statistics,
since a key that is nearly unique per row leaves the grouped split close
to a random one, and the grouped/random error ratio, since near a ceiling
an absolute drop can be small while the error rate multiplies.

Independent of whichever split_mode is configured for the main run:
always builds both splits from the raw data to compare them directly.

Accepts an already-loaded `combined` DataFrame so run_audit can share one
load across this, scenario_holdout_falsification, result_robustness_check,
and repeated_seed_falsification_check when several run together - each
independently reloading the full raw dataset from disk is a real cost at
full scale (a real failure this was built to avoid: a 70M-row config
running all three of these checks was reloading the same data three times
sequentially, contributing to repeated VM-level instability on a long run).
Still loads it itself when called standalone (e.g. every existing direct
unit test), so this is purely an optimization, not a behavior change.
"""

from __future__ import annotations

import pandas as pd

from ..data import dataset
from . import _groups, _metrics
from ._fit_score import fit_and_evaluate

# A grouped-split drop below this is read as "structurally ruling out
# session-correlated leakage as the explanation," not proof of zero leakage
# of any kind. The same value applies to every metric unless
# audit.materiality_thresholds.resplit_falsification sets it per metric.
MATERIAL_DROP_THRESHOLD = 0.01

_VERDICTS = {
    "flag": "the grouped split costs measurable performance beyond test-set sampling noise; "
            "information tied to the grouping key may be doing real work in the random split",
    "warning": "inconclusive: a drop exceeds its threshold only within its sampling margin at this "
               "test size, see repeated_seed_falsification_check",
    "ok": "the grouped split reproduces the random-split result: no evidence that information tied "
          "to the grouping key drives it (other grouping keys and shortcuts are not tested)",
}


def check(cfg: dict, seed: int = 0, combined: pd.DataFrame | None = None) -> dict:
    dataset_cfg = cfg["dataset"]
    label_col = cfg["schema"]["label_column"]
    if combined is None:
        combined = dataset.load_raw_combined(dataset_cfg, seed=cfg["random_seed"])
    groups = _groups.group_stats(combined, dataset_cfg["group_columns"])

    # Scored one split at a time, not both built up front: at full scale (hundreds
    # of millions of rows) holding combined plus both split pairs simultaneously -
    # five full-size DataFrames at once - is itself the dominant memory cost, a
    # real failure this was built to avoid, not a theoretical one. fit_and_evaluate
    # only returns a confusion matrix, so each split's train/test can be freed
    # before the next is built.
    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
    random_scores = fit_and_evaluate(random_train, random_test, label_col, cfg, seed=seed)
    del random_train, random_test

    grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg, seed=seed)
    grouped_scores = fit_and_evaluate(grouped_train, grouped_test, label_col, cfg, seed=seed)
    del grouped_train, grouped_test

    random_m, grouped_m = random_scores.metrics, grouped_scores.metrics
    margins = _metrics.gap_margins(random_scores, grouped_scores)
    thresholds = _metrics.thresholds(cfg, "resplit_falsification", MATERIAL_DROP_THRESHOLD)
    by_metric, verdicts = {}, {}
    for m in _metrics.METRICS:
        drop = random_m[m] - grouped_m[m]
        verdicts[m] = _metrics.single_comparison_verdict(drop, margins[m], thresholds[m])
        by_metric[m] = {
            "random": random_m[m], "grouped": grouped_m[m], "drop": drop,
            "sampling_margin": margins[m], "threshold": thresholds[m], "verdict": verdicts[m],
        }
    status = _metrics.combined_status(verdicts, cfg)
    error_ratio = _metrics.error_ratio(random_m["accuracy"], grouped_m["accuracy"])

    summary = (
        f"random-split accuracy={random_m['accuracy']:.4f}, grouped-split accuracy="
        f"{grouped_m['accuracy']:.4f} (drop={by_metric['accuracy']['drop']:+.4f}); "
        f"balanced accuracy drop={by_metric['balanced_accuracy']['drop']:+.4f}, macro-F1 drop="
        f"{by_metric['macro_f1']['drop']:+.4f} ({_metrics.describe(verdicts)}); "
        f"grouping key: {_groups.describe(groups)}; {_VERDICTS[status]}"
    )
    return {
        "check": "resplit_falsification", "status": status, "summary": summary,
        "details": {
            "random_accuracy": random_m["accuracy"], "grouped_accuracy": grouped_m["accuracy"],
            "drop": by_metric["accuracy"]["drop"], "sampling_margin": margins["accuracy"],
            "random_test_rows": random_scores.n, "grouped_test_rows": grouped_scores.n,
            "by_metric": by_metric, "error_ratio": error_ratio,
            "materiality_metrics": list(cfg["audit"]["materiality_metrics"]),
            "group_stats": groups,
        },
    }
