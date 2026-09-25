"""One-rule ("one-liner") solvability check.

Per Wu & Keogh 2021 (IEEE TKDE): most widely-used time-series anomaly
benchmarks (Yahoo, NASA, Numenta) are largely solvable by a single line of
code - one feature compared to one threshold - which means published
comparisons of sophisticated algorithms on them are measuring nothing more
than who found the same threshold. leakage_screen already reports that a
feature carries most of a random forest's importance, but a share-of-
importance number is abstract; this check names the winning rule in plain
language ("Dst Port <= 1024.5"), which is far harder to argue with. A
depth-1 decision tree (a "stump") is exactly a brute-force search over
every feature and threshold for the single best split, done in one cheap
fit rather than a manual loop.
"""

from __future__ import annotations

import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from .. import features

# Wu & Keogh don't give a numeric cutoff (their test is "can a human write this in
# one line"); a one-rule accuracy this high is the tabular-data equivalent - a
# threshold on a single feature is about as simple a rule as exists.
ACCURACY_FLAG_THRESHOLD = 0.95
MAX_FIT_ROWS = 200_000


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict, seed: int = 0) -> dict:
    """seed only varies the sample draw and the stump's own randomness -
    used by seed_sensitivity_check to test whether the flag/ok conclusion
    holds up across seeds, not by the default single-seed run.
    """
    label_col = cfg["schema"]["label_column"]
    cols = features.feature_columns(train_df, cfg)
    train_fit = train_df.sample(n=min(len(train_df), MAX_FIT_ROWS), random_state=seed)
    x_train, x_test = features.encode_aligned(train_fit, test_df, cols)
    y_train, y_test = train_fit[label_col], test_df[label_col]

    stump = DecisionTreeClassifier(max_depth=1, random_state=seed)
    stump.fit(x_train, y_train)
    tree = stump.tree_
    root_feature = tree.feature[0]

    if root_feature < 0:  # -2: the root is already a leaf - e.g. a single-class split
        return {
            "check": "one_rule_check", "status": "ok",
            "summary": "no single-feature rule found (fewer than two classes in the fitted sample)",
            "details": {},
        }

    rule = f"{x_train.columns[root_feature]} <= {tree.threshold[0]:.4g}"
    train_acc = float(stump.score(x_train, y_train))
    test_acc = float(stump.score(x_test, y_test))

    flagged = test_acc > ACCURACY_FLAG_THRESHOLD
    status = "flag" if flagged else "ok"
    summary = f"single rule '{rule}' reaches {test_acc:.1%} test accuracy ({train_acc:.1%} train)"
    if flagged:
        summary += ". This problem may be solvable without learning attack behavior"

    return {
        "check": "one_rule_check", "status": status, "summary": summary,
        "details": {"rule": rule, "train_accuracy": train_acc, "test_accuracy": test_acc},
    }
