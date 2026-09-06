import json
import time

from ids2eval import run_manager


def test_create_run_dir_is_unique_across_rapid_calls(tmp_path):
    dirs = [run_manager.create_run_dir(tmp_path) for _ in range(5)]
    assert len(set(dirs)) == 5
    assert all(d.exists() for d in dirs)


def test_cleanup_old_runs_keeps_only_the_most_recent(tmp_path):
    for _ in range(5):
        run_manager.create_run_dir(tmp_path)
        time.sleep(0.001)
    run_manager.cleanup_old_runs(tmp_path, keep_runs=2)
    remaining = list((tmp_path / "runs").iterdir())
    assert len(remaining) == 2


def test_cleanup_old_runs_keep_none_means_keep_all(tmp_path):
    for _ in range(3):
        run_manager.create_run_dir(tmp_path)
    run_manager.cleanup_old_runs(tmp_path, keep_runs=None)
    assert len(list((tmp_path / "runs").iterdir())) == 3


def test_cleanup_old_runs_never_touches_cache_dir(tmp_path):
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    (cache_dir / "train.parquet").write_text("not really parquet, just checking survival")

    for _ in range(3):
        run_manager.create_run_dir(tmp_path)
    run_manager.cleanup_old_runs(tmp_path, keep_runs=1)

    assert (cache_dir / "train.parquet").exists()


def test_write_environment_info_includes_key_packages(tmp_path):
    run_manager.write_environment_info(tmp_path)
    info = json.loads((tmp_path / "environment.json").read_text())
    assert "python_version" in info
    assert info["packages"]["pandas"] != "not installed"
    assert info["packages"]["scikit-learn"] != "not installed"


def test_write_resolved_config_round_trips(tmp_path):
    cfg = {"dataset": {"name": "x"}, "output": {"dir": "./output"}}
    run_manager.write_resolved_config(tmp_path, cfg)
    written = json.loads((tmp_path / "resolved_config.json").read_text())
    assert written == cfg


def test_write_dataset_fingerprint_content(tmp_path):
    import pandas as pd
    train_df = pd.DataFrame({"F1": [1, 2, 3], "Label": ["A", "B", "A"]})
    test_df = pd.DataFrame({"F1": [4, 5], "Label": ["A", "B"]})
    cfg = {"schema": {"label_column": "Label", "attack_category_column": None, "drop_columns": []}}

    run_manager.write_dataset_fingerprint(tmp_path, train_df, test_df, cfg)
    fp = json.loads((tmp_path / "dataset_fingerprint.json").read_text())

    assert fp["train_rows"] == 3
    assert fp["test_rows"] == 2
    assert fp["feature_count"] == 1
    assert fp["train_class_distribution"] == {"A": 2, "B": 1}
    assert "train_content_hash" in fp and "test_content_hash" in fp


def test_dataset_fingerprint_hash_changes_with_content(tmp_path):
    import pandas as pd
    cfg = {"schema": {"label_column": "Label", "attack_category_column": None, "drop_columns": []}}
    df_a = pd.DataFrame({"F1": [1, 2], "Label": ["A", "B"]})
    df_b = pd.DataFrame({"F1": [1, 3], "Label": ["A", "B"]})  # one value different

    run_manager.write_dataset_fingerprint(tmp_path, df_a, df_a, cfg)
    fp_a = json.loads((tmp_path / "dataset_fingerprint.json").read_text())
    run_manager.write_dataset_fingerprint(tmp_path, df_b, df_b, cfg)
    fp_b = json.loads((tmp_path / "dataset_fingerprint.json").read_text())

    assert fp_a["train_content_hash"] != fp_b["train_content_hash"]


def test_write_run_status_completed(tmp_path):
    run_manager.write_run_status(tmp_path, status="completed")
    status = json.loads((tmp_path / "run_status.json").read_text())
    assert status["status"] == "completed"
    assert status["failed_stage"] is None


def test_write_run_status_failed(tmp_path):
    run_manager.write_run_status(tmp_path, status="failed", failed_stage="benchmark", error="boom")
    status = json.loads((tmp_path / "run_status.json").read_text())
    assert status["status"] == "failed"
    assert status["failed_stage"] == "benchmark"
    assert status["error"] == "boom"


def test_environment_info_includes_ids2eval_version(tmp_path):
    run_manager.write_environment_info(tmp_path)
    info = json.loads((tmp_path / "environment.json").read_text())
    assert "ids2eval" in info
    assert "version" in info["ids2eval"]
