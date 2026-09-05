import pandas as pd

from ids2eval.label_grouping import apply_attack_type_mapping


def test_partial_mapping_merges_named_categories_only(base_cfg):
    base_cfg["schema"]["attack_category_column"] = "AttackType"
    base_cfg["label_grouping"]["attack_type_mapping"] = {
        "DoS Hulk": "DoS", "DoS GoldenEye": "DoS",
    }
    train_df = pd.DataFrame({"AttackType": ["DoS Hulk", "DoS GoldenEye", "PortScan", "Benign"]})
    test_df = pd.DataFrame({"AttackType": ["DoS Hulk", "PortScan"]})

    train_out, test_out = apply_attack_type_mapping(train_df, test_df, base_cfg)

    assert train_out["AttackType"].tolist() == ["DoS", "DoS", "PortScan", "Benign"]
    assert test_out["AttackType"].tolist() == ["DoS", "PortScan"]


def test_empty_mapping_is_a_no_op(base_cfg):
    base_cfg["schema"]["attack_category_column"] = "AttackType"
    train_df = pd.DataFrame({"AttackType": ["DoS", "Benign"]})
    test_df = pd.DataFrame({"AttackType": ["Benign"]})

    train_out, test_out = apply_attack_type_mapping(train_df, test_df, base_cfg)

    assert train_out["AttackType"].tolist() == ["DoS", "Benign"]
    assert test_out["AttackType"].tolist() == ["Benign"]


def test_does_not_mutate_input_dataframes(base_cfg):
    base_cfg["schema"]["attack_category_column"] = "AttackType"
    base_cfg["label_grouping"]["attack_type_mapping"] = {"DoS Hulk": "DoS"}
    train_df = pd.DataFrame({"AttackType": ["DoS Hulk"]})
    test_df = pd.DataFrame({"AttackType": ["DoS Hulk"]})

    apply_attack_type_mapping(train_df, test_df, base_cfg)

    assert train_df["AttackType"].tolist() == ["DoS Hulk"]
    assert test_df["AttackType"].tolist() == ["DoS Hulk"]
