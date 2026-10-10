"""Resplit falsification test (paper Section 3.5).

The nearest-neighbor test alone can't distinguish "this class is
inherently homogeneous" from "a different split would reveal real
difficulty that random sampling happens to hide", both hypotheses look
identical under random sampling. Constructing a non-random split along a
dimension the random split ignores (session/group identity) and
observing whether accuracy changes breaks that symmetry: if
session-correlated leakage across the random split's boundary had been
doing real work, the grouped split should cost measurable accuracy.

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
from . import _materiality
from ._fit_score import fit_and_score

# A grouped-split accuracy drop below this is read as "structurally
# ruling out session-correlated leakage as the explanation," not proof
# of zero leakage of any kind. Overridable via audit.materiality_thresholds.
# resplit_falsification.
MATERIAL_DROP_THRESHOLD = 0.01


def check(cfg: dict, seed: int = 0, combined: pd.DataFrame | None = None) -> dict:
    dataset_cfg = cfg["dataset"]
    label_col = cfg["schema"]["label_column"]
    if combined is None:
        combined = dataset.load_raw_combined(dataset_cfg, seed=cfg["random_seed"])

    # Scored one split at a time, not both built up front: at full scale (hundreds
    # of millions of rows) holding combined plus both split pairs simultaneously -
    # five full-size DataFrames at once - is itself the dominant memory cost, a
    # real failure this was built to avoid, not a theoretical one. fit_and_score
    # only needs the float back, so each split's train/test can be freed before
    # the next is built.
    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
    random_acc = fit_and_score(random_train, random_test, label_col, cfg, seed=seed)
    n_random = len(random_test)
    del random_train, random_test

    grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg, seed=seed)
    grouped_acc = fit_and_score(grouped_train, grouped_test, label_col, cfg, seed=seed)
    n_grouped = len(grouped_test)
    del grouped_train, grouped_test
    drop = random_acc - grouped_acc

    threshold = _materiality.threshold(cfg, "resplit_falsification", MATERIAL_DROP_THRESHOLD)
    # One comparison on finite test sets: a drop only counts as material once it
    # clears the threshold by more than its own sampling margin. A drop above the
    # threshold but within that margin is reported as inconclusive (warning).
    margin = _materiality.accuracy_gap_margin(random_acc, n_random, grouped_acc, n_grouped)
    if drop - margin > threshold:
        status, verdict = "flag", (
            "grouped split costs measurable accuracy beyond test-set sampling noise, "
            "session-correlated leakage in the random split may be doing real work"
        )
    elif drop > threshold:
        status, verdict = "warning", (
            f"the drop exceeds the {threshold:.2f} threshold but lies within its sampling margin "
            f"(+/-{margin:.4f}) at this test size; inconclusive, see repeated_seed_falsification_check"
        )
    else:
        status, verdict = "ok", (
            "grouped split reproduces random-split accuracy: no evidence that information tied "
            "to the grouping key drives the result (other grouping keys and shortcuts are not tested)"
        )
    summary = (
        f"random-split accuracy={random_acc:.4f}, grouped-split accuracy={grouped_acc:.4f} "
        f"(drop={drop:+.4f}); {verdict}"
    )
    return {
        "check": "resplit_falsification", "status": status, "summary": summary,
        "details": {"random_accuracy": random_acc, "grouped_accuracy": grouped_acc, "drop": drop,
                    "sampling_margin": margin, "random_test_rows": n_random, "grouped_test_rows": n_grouped},
    }
