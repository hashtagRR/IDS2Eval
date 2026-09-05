import time

import pandas as pd

from ids2eval import cache


def _cfg(base_cfg, raw_file):
    base_cfg["dataset"]["raw_files"] = [str(raw_file)]
    base_cfg["output"]["dir"] = str(raw_file.parent / "output")
    return base_cfg


def test_cache_miss_when_nothing_cached_yet(base_cfg, tmp_path):
    raw_file = tmp_path / "data.csv"
    raw_file.write_text("Label,F\nA,1\n")
    cfg = _cfg(base_cfg, raw_file)
    assert cache.try_load(cfg) is None


def test_cache_hit_returns_saved_frames(base_cfg, tmp_path):
    raw_file = tmp_path / "data.csv"
    raw_file.write_text("Label,F\nA,1\n")
    cfg = _cfg(base_cfg, raw_file)

    train_df = pd.DataFrame({"Label": ["A", "B"], "F": [1, 2]})
    test_df = pd.DataFrame({"Label": ["A"], "F": [3]})
    cache.save(train_df, test_df, cfg)

    loaded = cache.try_load(cfg)
    assert loaded is not None
    loaded_train, loaded_test = loaded
    assert loaded_train.equals(train_df)
    assert loaded_test.equals(test_df)


def test_cache_invalidated_by_config_change(base_cfg, tmp_path):
    raw_file = tmp_path / "data.csv"
    raw_file.write_text("Label,F\nA,1\n")
    cfg = _cfg(base_cfg, raw_file)
    cache.save(pd.DataFrame({"Label": ["A"], "F": [1]}), pd.DataFrame({"Label": ["A"], "F": [1]}), cfg)
    assert cache.try_load(cfg) is not None

    cfg["dataset"]["split_ratio"] = 0.5  # was 0.8 (default) when cached
    assert cache.try_load(cfg) is None


def test_cache_invalidated_when_input_file_changes(base_cfg, tmp_path):
    raw_file = tmp_path / "data.csv"
    raw_file.write_text("Label,F\nA,1\n")
    cfg = _cfg(base_cfg, raw_file)
    cache.save(pd.DataFrame({"Label": ["A"], "F": [1]}), pd.DataFrame({"Label": ["A"], "F": [1]}), cfg)
    assert cache.try_load(cfg) is not None

    time.sleep(0.01)
    raw_file.write_text("Label,F\nA,1\nB,2\n")  # source file changed after caching
    assert cache.try_load(cfg) is None


def test_fingerprint_stable_across_repeated_calls(base_cfg, tmp_path):
    raw_file = tmp_path / "data.csv"
    raw_file.write_text("Label,F\nA,1\n")
    cfg = _cfg(base_cfg, raw_file)
    assert cache.compute_fingerprint(cfg) == cache.compute_fingerprint(cfg)
