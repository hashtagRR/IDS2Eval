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
"""

from __future__ import annotations

from ..data import dataset
from . import _materiality
from ._fit_score import fit_and_score

# A grouped-split accuracy drop below this is read as "structurally
# ruling out session-correlated leakage as the explanation," not proof
# of zero leakage of any kind. Overridable via audit.materiality_thresholds.
# resplit_falsification.
MATERIAL_DROP_THRESHOLD = 0.01


def check(cfg: dict, seed: int = 0) -> dict:
    dataset_cfg = cfg["dataset"]
    label_col = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(dataset_cfg)

    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
    grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg, seed=seed)

    random_acc = fit_and_score(random_train, random_test, label_col, cfg, seed=seed)
    grouped_acc = fit_and_score(grouped_train, grouped_test, label_col, cfg, seed=seed)
    drop = random_acc - grouped_acc

    threshold = _materiality.threshold(cfg, "resplit_falsification", MATERIAL_DROP_THRESHOLD)
    material = drop > threshold
    status = "flag" if material else "ok"
    summary = (
        f"random-split accuracy={random_acc:.4f}, grouped-split accuracy={grouped_acc:.4f} "
        f"(drop={drop:+.4f}); "
        + (
            "grouped split costs measurable accuracy, session-correlated leakage in the "
            "random split may be doing real work"
            if material else
            "grouped split reproduces random-split accuracy, consistent with inherent class "
            "homogeneity rather than a split-artifact explanation"
        )
    )
    return {
        "check": "resplit_falsification", "status": status, "summary": summary,
        "details": {"random_accuracy": random_acc, "grouped_accuracy": grouped_acc, "drop": drop},
    }
