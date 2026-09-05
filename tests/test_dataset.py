import pandas as pd
import pytest

from ids2eval import dataset


def test_load_split_pre_split_files(tmp_path, base_cfg):
    train_path, test_path = tmp_path / "train.csv", tmp_path / "test.csv"
    pd.DataFrame({"Label": ["A", "B"], "F": [1, 2]}).to_csv(train_path, index=False)
    pd.DataFrame({"Label": ["A"], "F": [3]}).to_csv(test_path, index=False)
    base_cfg["dataset"]["train_file"] = str(train_path)
    base_cfg["dataset"]["test_file"] = str(test_path)

    train_df, test_df = dataset.load_split(base_cfg)
    assert len(train_df) == 2
    assert len(test_df) == 1


def test_random_split_preserves_row_count(base_cfg, synth_data):
    base_cfg["dataset"]["split_ratio"] = 0.7
    train, test = dataset._random_split(synth_data, "Label", base_cfg["dataset"])
    assert len(train) + len(test) == len(synth_data)


def test_grouped_split_has_zero_group_overlap(base_cfg, synth_data):
    dataset_cfg = base_cfg["dataset"]
    dataset_cfg["group_columns"] = ["SrcIP"]
    dataset_cfg["split_ratio"] = 0.5
    train, test = dataset._grouped_split(synth_data, "Label", dataset_cfg)
    assert set(train["SrcIP"]) & set(test["SrcIP"]) == set()


def test_grouped_split_raises_if_group_columns_missing(base_cfg, synth_data):
    dataset_cfg = base_cfg["dataset"]
    dataset_cfg["group_columns"] = ["NoSuchColumn"]
    with pytest.raises(ValueError, match="are present in the loaded data"):
        dataset._grouped_split(synth_data, "Label", dataset_cfg)


def test_dedup_removes_train_internal_duplicates(base_cfg, synth_data):
    train_df = synth_data.copy()
    test_df = pd.DataFrame(columns=synth_data.columns)
    deduped_train, deduped_test, stats = dataset.dedup(train_df, test_df, base_cfg)
    assert stats["train_duplicates_dropped"] == 10  # planted in the synth_data fixture
    assert len(deduped_train) == len(train_df) - 10


def test_dedup_removes_test_rows_leaking_train_features(base_cfg):
    train_df = pd.DataFrame({"F": [1, 2, 3], "Label": ["A", "A", "B"]})
    test_df = pd.DataFrame({"F": [1, 99], "Label": ["A", "B"]})  # first row duplicates train
    _, deduped_test, stats = dataset.dedup(train_df, test_df, base_cfg)
    assert stats["test_leakage_dropped"] == 1
    assert len(deduped_test) == 1
    assert deduped_test["F"].tolist() == [99]


def test_dedup_ignores_label_when_comparing_features(base_cfg):
    # same features, different label -> still a leakage drop per dataset.dedup's
    # documented behavior (a model only ever sees features, not labels)
    train_df = pd.DataFrame({"F": [1], "Label": ["A"]})
    test_df = pd.DataFrame({"F": [1], "Label": ["B"]})
    _, deduped_test, stats = dataset.dedup(train_df, test_df, base_cfg)
    assert stats["test_leakage_dropped"] == 1
    assert len(deduped_test) == 0


def test_validate_loaded_raises_on_duplicate_columns(base_cfg):
    train_df = pd.DataFrame([[1, 2, "A"]], columns=pd.Index(["F", "F", "Label"]))
    test_df = pd.DataFrame({"F": [1], "Label": ["A"]})
    with pytest.raises(ValueError, match="duplicate column names"):
        dataset.validate_loaded(train_df, test_df, base_cfg)


def test_validate_loaded_raises_when_label_column_missing(base_cfg):
    train_df = pd.DataFrame({"F": [1], "NotLabel": ["A"]})
    test_df = pd.DataFrame({"F": [1], "Label": ["A"]})
    with pytest.raises(ValueError, match="not found in the loaded train data"):
        dataset.validate_loaded(train_df, test_df, base_cfg)


def test_validate_loaded_raises_on_disjoint_schemas(base_cfg):
    train_df = pd.DataFrame({"F1": [1], "Label": ["A"]})
    test_df = pd.DataFrame({"F2": [1], "Label": ["A"]})
    with pytest.raises(ValueError, match="share no feature columns"):
        dataset.validate_loaded(train_df, test_df, base_cfg)


def test_validate_loaded_passes_on_healthy_data(base_cfg):
    train_df = pd.DataFrame({"F1": [1], "Label": ["A"]})
    test_df = pd.DataFrame({"F1": [2], "Label": ["B"]})
    dataset.validate_loaded(train_df, test_df, base_cfg)  # should not raise
