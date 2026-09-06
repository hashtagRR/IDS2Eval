import re

import pytest

from ids2eval.config import load_config, validate_config


def test_defaults_merge(tmp_path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        "dataset:\n  name: x\n  raw_files: [a.csv]\n  group_columns: [g]\n"
        "schema:\n  label_column: Label\n"
    )
    cfg = load_config(path)
    assert cfg["preprocessing"]["scaling"] == "standard"  # default preserved
    assert cfg["classifiers"]["list"] == "all"


def test_requires_dataset_name(base_cfg):
    base_cfg["dataset"]["name"] = None
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    with pytest.raises(ValueError, match=re.escape("dataset.name is required")):
        validate_config(base_cfg)


def test_requires_exactly_one_data_source(base_cfg):
    base_cfg["dataset"]["raw_files"] = []
    base_cfg["dataset"]["train_file"] = None
    with pytest.raises(ValueError, match="exactly one of raw_files"):
        validate_config(base_cfg)

    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["dataset"]["train_file"] = "train.csv"
    base_cfg["dataset"]["test_file"] = "test.csv"
    with pytest.raises(ValueError, match="exactly one of raw_files"):
        validate_config(base_cfg)


def test_grouped_split_requires_group_columns(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["dataset"]["split_mode"] = "grouped"
    base_cfg["audit"]["resplit_falsification"] = False
    with pytest.raises(ValueError, match="group_columns is required"):
        validate_config(base_cfg)


def test_max_rows_requires_chunk_size(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["dataset"]["max_rows"] = 1000
    base_cfg["audit"]["resplit_falsification"] = False
    with pytest.raises(ValueError, match=re.escape("max_rows requires dataset.chunk_size")):
        validate_config(base_cfg)


def test_chunk_size_and_max_rows_valid_together(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["dataset"]["chunk_size"] = 500
    base_cfg["dataset"]["max_rows"] = 1000
    base_cfg["audit"]["resplit_falsification"] = False
    validate_config(base_cfg)  # should not raise


def test_resplit_falsification_requires_raw_and_groups(base_cfg):
    base_cfg["dataset"]["train_file"] = "train.csv"
    base_cfg["dataset"]["test_file"] = "test.csv"
    with pytest.raises(ValueError, match="resplit_falsification requires"):
        validate_config(base_cfg)


def test_v2_reference_checks_require_reference_dataset(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["audit"]["synthetic_realism_check"] = True
    with pytest.raises(ValueError, match="reference_dataset is required"):
        validate_config(base_cfg)


def test_attack_type_mapping_requires_attack_category_column(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["label_grouping"]["attack_type_mapping"] = {"DoS Hulk": "DoS"}
    with pytest.raises(ValueError, match=re.escape("attack_type_mapping requires schema.attack_category_column")):
        validate_config(base_cfg)


def test_known_issue_lookup_does_not_require_reference_dataset(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["audit"]["known_issue_lookup"] = True
    validate_config(base_cfg)  # should not raise


def test_unknown_classifier_rejected(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["classifiers"]["list"] = ["NotAClassifier"]
    with pytest.raises(ValueError, match="unknown entries"):
        validate_config(base_cfg)


def test_invalid_scaling_rejected(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["scaling"] = "bogus"
    with pytest.raises(ValueError, match="invalid entries"):
        validate_config(base_cfg)


def test_scaling_accepts_a_list_of_strategies(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["scaling"] = ["none", "standard", "robust"]
    validate_config(base_cfg)  # should not raise


def test_scaling_list_rejects_invalid_entries(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["scaling"] = ["standard", "bogus"]
    with pytest.raises(ValueError, match="invalid entries"):
        validate_config(base_cfg)


def test_scaling_rejects_empty_list(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["scaling"] = []
    with pytest.raises(ValueError, match="must not be an empty list"):
        validate_config(base_cfg)


def test_sampling_accepts_a_list_of_strategies(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["sampling"]["binary"] = ["none", "smote", "smoteenn"]
    validate_config(base_cfg)  # should not raise


def test_sampling_list_rejects_invalid_entries(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["sampling"]["binary"] = ["smote", "bogus"]
    with pytest.raises(ValueError, match="invalid entries"):
        validate_config(base_cfg)


def test_sampling_rejects_empty_list(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["preprocessing"]["sampling"]["binary"] = []
    with pytest.raises(ValueError, match="must not be an empty list"):
        validate_config(base_cfg)


def test_keep_runs_rejects_non_positive(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["output"]["keep_runs"] = 0
    with pytest.raises(ValueError, match="keep_runs must be a positive integer"):
        validate_config(base_cfg)


def test_keep_runs_null_means_keep_all(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["output"]["keep_runs"] = None
    validate_config(base_cfg)  # should not raise


def test_write_scorecard_plot_passes_when_matplotlib_available(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["output"]["write_scorecard_plot"] = True
    validate_config(base_cfg)  # should not raise - matplotlib is a dev/test dependency


def test_write_scorecard_plot_fails_fast_without_matplotlib(base_cfg, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "matplotlib", None)  # simulate it not being installed
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["output"]["write_scorecard_plot"] = True
    with pytest.raises(ValueError, match='pip install "ids2eval\\[plots\\]"'):
        validate_config(base_cfg)


def test_random_seed_must_be_an_integer(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["random_seed"] = "not-an-int"
    with pytest.raises(ValueError, match="random_seed must be an integer"):
        validate_config(base_cfg)


def test_random_seed_rejects_bool(base_cfg):
    # bool is technically an int subclass in Python - guard against it explicitly
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    base_cfg["random_seed"] = True
    with pytest.raises(ValueError, match="random_seed must be an integer"):
        validate_config(base_cfg)


def test_random_seed_default_is_valid(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    validate_config(base_cfg)  # should not raise
