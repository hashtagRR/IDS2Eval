import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from ids2eval.audit import _groups, _metrics


@pytest.mark.parametrize("seed", range(20))
def test_metrics_match_scikit_learn(seed):
    rng = np.random.default_rng(seed)
    y = rng.choice(["a", "b", "c", "d"], 200, p=[0.7, 0.2, 0.08, 0.02])
    p = np.where(rng.random(200) < 0.8, y, rng.choice(["a", "b", "c", "e"], 200))
    got = _metrics.scores_from_predictions(y, p).metrics
    assert got["accuracy"] == pytest.approx(accuracy_score(y, p))
    with pytest.warns(UserWarning):  # scikit-learn warns about the predicted-only class "e"
        assert got["balanced_accuracy"] == pytest.approx(balanced_accuracy_score(y, p))
    assert got["macro_f1"] == pytest.approx(f1_score(y, p, average="macro", zero_division=0))


def test_gap_margin_shrinks_with_test_size():
    small = _metrics.Scores(("a", "b"), np.array([[40, 10], [10, 40]]))
    large = _metrics.Scores(("a", "b"), np.array([[4000, 1000], [1000, 4000]]))
    for metric in _metrics.METRICS:
        assert _metrics.gap_margins(large, large)[metric] < _metrics.gap_margins(small, small)[metric]


def test_verdict_rules():
    assert _metrics.single_comparison_verdict(0.20, 0.05, 0.10) == "flag"
    assert _metrics.single_comparison_verdict(0.12, 0.05, 0.10) == "warning"
    assert _metrics.single_comparison_verdict(0.05, 0.05, 0.10) == "ok"
    assert _metrics.interval_verdict(0.02, 0.05, 0.01) == "flag"
    assert _metrics.interval_verdict(-0.01, 0.005, 0.01) == "ok"
    assert _metrics.interval_verdict(0.0, 0.02, 0.01) == "warning"


def test_thresholds_accept_a_single_value_or_a_per_metric_mapping():
    cfg = {"audit": {"materiality_thresholds": {}}}
    assert _metrics.thresholds(cfg, "x", 0.01) == dict.fromkeys(_metrics.METRICS, 0.01)
    cfg["audit"]["materiality_thresholds"] = {"x": 0.02}
    assert _metrics.thresholds(cfg, "x", 0.01) == dict.fromkeys(_metrics.METRICS, 0.02)
    cfg["audit"]["materiality_thresholds"] = {"x": {"macro_f1": 0.05}}
    assert _metrics.thresholds(cfg, "x", 0.01)["macro_f1"] == 0.05
    assert _metrics.thresholds(cfg, "x", 0.01)["accuracy"] == 0.01
    tiers = {"warning": 0.08, "flag": 0.15}
    cfg["audit"]["materiality_thresholds"] = {"y": tiers}
    assert _metrics.thresholds(cfg, "y", None)["balanced_accuracy"] == tiers


def test_error_ratio():
    assert _metrics.error_ratio(0.9995, 0.994) == pytest.approx(12.0)
    assert _metrics.error_ratio(1.0, 0.9) is None


def test_group_stats_on_a_near_unique_key():
    df = pd.DataFrame({"k": [1, 1, 2, 3, 4, 5]})
    stats = _groups.group_stats(df, ["k"])
    assert stats["groups"] == 5
    assert stats["singleton_group_share"] == pytest.approx(0.8)
    assert stats["rows_in_singleton_groups"] == pytest.approx(4 / 6)
    assert stats["size_max"] == 2


def test_class_support_lists_classes_a_split_leaves_out():
    train = pd.Series(["a", "a", "b"])
    test = pd.Series(["a", "c"])
    missing = _groups.class_support(train, test)
    assert missing == {"missing_from_train": ["c"], "missing_from_test": ["b"]}
    assert "no training rows: ['c']" in _groups.describe_class_loss(missing)
    assert _groups.describe_class_loss({"missing_from_train": [], "missing_from_test": []}) == ""
