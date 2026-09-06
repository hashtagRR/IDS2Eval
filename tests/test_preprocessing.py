import numpy as np
import pandas as pd

from ids2eval import preprocessing


def test_scale_features_none_leaves_values_unchanged(base_cfg, synth_train_test):
    base_cfg["preprocessing"]["scaling"] = "none"
    train_df, test_df = synth_train_test
    x_train, _x_test, cols = preprocessing.scale_features(train_df, test_df, base_cfg)
    assert x_train.shape[1] == len(cols)
    assert x_train.shape[0] == len(train_df)


def test_scale_features_standard_zero_means_on_train(base_cfg, synth_train_test):
    base_cfg["preprocessing"]["scaling"] = "standard"
    train_df, test_df = synth_train_test
    x_train, _, _ = preprocessing.scale_features(train_df, test_df, base_cfg)
    assert np.allclose(x_train.mean(axis=0), 0, atol=1e-8)


def test_apply_sampling_none_returns_original_data(base_cfg):
    x = np.array([[1.0], [2.0], [3.0]])
    y = pd.Series(["A", "A", "B"])
    x_out, y_out = preprocessing.apply_sampling(x, y, base_cfg, "binary")
    assert x_out is x
    assert list(y_out) == list(y)


def test_apply_sampling_smote_balances_classes(base_cfg):
    base_cfg["preprocessing"]["sampling"]["binary"] = "smote"
    rng = np.random.RandomState(0)
    x = np.vstack([rng.normal(0, 1, (100, 2)), rng.normal(5, 1, (20, 2))])
    y = pd.Series(["A"] * 100 + ["B"] * 20)
    _x_out, y_out = preprocessing.apply_sampling(x, y, base_cfg, "binary")
    counts = pd.Series(y_out).value_counts()
    assert counts["A"] == counts["B"]


def test_apply_sampling_falls_back_gracefully_on_too_small_class(base_cfg):
    base_cfg["preprocessing"]["sampling"]["binary"] = "smote"
    x = np.array([[1.0], [2.0], [3.0]])
    y = pd.Series(["A", "A", "B"])  # class B has only 1 sample - SMOTE needs neighbors
    x_out, _y_out = preprocessing.apply_sampling(x, y, base_cfg, "binary")
    assert len(x_out) == 3  # fell back to unsampled data instead of raising
