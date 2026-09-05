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
