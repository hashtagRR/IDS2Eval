"""Cross-dataset drift check (v2, opt-in).

Trains on this dataset and evaluates on a reference dataset
(audit.reference_dataset) in a unified feature space, comparing accuracy
against the same model's in-dataset test accuracy. A large drop is a
specific, checkable signature that the model learned dataset-specific
artifacts rather than generalizable attack behavior — the pattern
documented across BoT-IoT/TON_IoT/UNSW-NB15 cross-dataset evaluations.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

from .. import chunked_io, features

MAX_FIT_ROWS = 200_000
# An accuracy drop beyond this crossing datasets is read as evidence of
# dataset-specific overfitting rather than ordinary generalization noise.
MATERIAL_DROP_THRESHOLD = 0.10


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    dataset_cfg = cfg["dataset"]
    ref_df = chunked_io.load_file(
        cfg["audit"]["reference_dataset"], dataset_cfg["chunk_size"], dataset_cfg["max_rows"]
    )

    label_col = cfg["schema"]["label_column"]
    if label_col not in ref_df.columns:
        return {
            "check": "cross_dataset_drift_check", "status": "warning",
            "summary": f"reference_dataset has no '{label_col}' column, cannot compute cross-dataset accuracy",
            "details": {},
        }

    cols = [c for c in features.feature_columns(train_df, cfg) if c in ref_df.columns]
    if not cols:
        return {
            "check": "cross_dataset_drift_check", "status": "warning",
            "summary": "no feature columns in common with reference_dataset", "details": {},
        }

    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=0)
    x_train, (x_test, x_ref) = features.encode_multi(train_fit, [test_df, ref_df], cols)

    clf = RandomForestClassifier(n_estimators=100, random_state=0, n_jobs=-1)
    clf.fit(x_train, train_fit[label_col])

    in_dataset_acc = float(accuracy_score(test_df[label_col], clf.predict(x_test)))
    cross_dataset_acc = float(accuracy_score(ref_df[label_col], clf.predict(x_ref)))
    drop = in_dataset_acc - cross_dataset_acc

    flagged = drop > MATERIAL_DROP_THRESHOLD
    status = "flag" if flagged else "ok"
    summary = (
        f"in-dataset accuracy={in_dataset_acc:.4f}, cross-dataset (reference_dataset) "
        f"accuracy={cross_dataset_acc:.4f} (drop={drop:+.4f}); "
        + (
            "material drop crossing datasets — model likely learned dataset-specific "
            "artifacts rather than generalizable attack behavior"
            if flagged else
            "no material drop crossing datasets"
        )
    )
    return {
        "check": "cross_dataset_drift_check", "status": status, "summary": summary,
        "details": {"in_dataset_accuracy": in_dataset_acc, "cross_dataset_accuracy": cross_dataset_acc, "drop": drop},
    }
