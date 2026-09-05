import pandas as pd

from ids2eval import features


def test_feature_columns_excludes_label_and_drop_columns(base_cfg):
    base_cfg["schema"]["drop_columns"] = ["id"]
    base_cfg["schema"]["attack_category_column"] = "attack_cat"
    df = pd.DataFrame({"id": [1], "Label": ["A"], "attack_cat": ["x"], "F1": [1.0]})
    assert features.feature_columns(df, base_cfg) == ["F1"]


def test_encode_aligned_unseen_category_maps_to_minus_one():
    train_df = pd.DataFrame({"cat": ["a", "b"]})
    test_df = pd.DataFrame({"cat": ["a", "unseen"]})
    train_out, test_out = features.encode_aligned(train_df, test_df, ["cat"])
    assert test_out["cat"].tolist()[1] == -1
    assert train_out["cat"].tolist()[0] == test_out["cat"].tolist()[0]  # "a" encodes the same on both sides


def test_encode_multi_uses_same_categories_across_all_targets():
    base_df = pd.DataFrame({"cat": ["x", "y", "z"]})
    other1 = pd.DataFrame({"cat": ["y", "unseen"]})
    other2 = pd.DataFrame({"cat": ["z"]})
    base_out, (out1, out2) = features.encode_multi(base_df, [other1, other2], ["cat"])
    y_code = base_out["cat"].tolist()[1]
    z_code = base_out["cat"].tolist()[2]
    assert out1["cat"].tolist() == [y_code, -1]
    assert out2["cat"].tolist() == [z_code]


def test_encode_aligned_numeric_columns_pass_through():
    train_df = pd.DataFrame({"n": [1, 2, 3]})
    test_df = pd.DataFrame({"n": [4, 5]})
    train_out, test_out = features.encode_aligned(train_df, test_df, ["n"])
    assert train_out["n"].tolist() == [1, 2, 3]
    assert test_out["n"].tolist() == [4, 5]
