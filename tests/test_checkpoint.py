import numpy as np

from ids2eval.audit import _checkpoint


def test_load_returns_empty_dict_when_nothing_checkpointed_yet(tmp_path):
    assert _checkpoint.load(str(tmp_path / "checkpoint.json")) == {}


def test_save_and_get_check_round_trips(tmp_path):
    path = str(tmp_path / "checkpoint.json")
    finding = {"check": "dedup_check", "status": "ok", "summary": "x", "details": {}}
    _checkpoint.save_check(path, "dedup_check", finding)
    assert _checkpoint.get_check(path, "dedup_check") == finding


def test_get_check_returns_none_for_an_uncheckpointed_check(tmp_path):
    path = str(tmp_path / "checkpoint.json")
    _checkpoint.save_check(path, "dedup_check", {"check": "dedup_check"})
    assert _checkpoint.get_check(path, "leakage_screen") is None


def test_save_check_preserves_other_already_checkpointed_checks(tmp_path):
    path = str(tmp_path / "checkpoint.json")
    _checkpoint.save_check(path, "dedup_check", {"check": "dedup_check"})
    _checkpoint.save_check(path, "leakage_screen", {"check": "leakage_screen"})
    assert _checkpoint.get_check(path, "dedup_check") == {"check": "dedup_check"}
    assert _checkpoint.get_check(path, "leakage_screen") == {"check": "leakage_screen"}


def test_seed_progress_round_trips_and_accumulates(tmp_path):
    path = str(tmp_path / "checkpoint.json")
    _checkpoint.save_seed_progress(path, "repeated_seed_falsification_check", 0, 0.01)
    _checkpoint.save_seed_progress(path, "repeated_seed_falsification_check", 1, -0.002)
    assert _checkpoint.get_seed_progress(path, "repeated_seed_falsification_check") == {
        0: 0.01, 1: -0.002,
    }


def test_get_seed_progress_empty_when_nothing_saved(tmp_path):
    path = str(tmp_path / "checkpoint.json")
    assert _checkpoint.get_seed_progress(path, "repeated_seed_falsification_check") == {}


def test_clear_removes_the_file(tmp_path):
    path = str(tmp_path / "checkpoint.json")
    _checkpoint.save_check(path, "dedup_check", {"check": "dedup_check"})
    _checkpoint.clear(path)
    assert _checkpoint.load(path) == {}


def test_clear_is_a_no_op_when_nothing_exists(tmp_path):
    path = str(tmp_path / "does_not_exist" / "checkpoint.json")
    _checkpoint.clear(path)  # must not raise


def test_save_check_handles_numpy_scalars_in_details(tmp_path):
    # Real findings often carry numpy bool/int/float scalars (most checks compute over
    # pandas/numpy data) - plain json.dumps can't serialize those on its own.
    path = str(tmp_path / "checkpoint.json")
    finding = {
        "check": "data_integrity_check", "status": "ok", "summary": "x",
        "details": {"has_missing": np.bool_(False), "count": np.int64(3), "rate": np.float64(0.5)},
    }
    _checkpoint.save_check(path, "data_integrity_check", finding)
    loaded = _checkpoint.get_check(path, "data_integrity_check")
    assert loaded["details"] == {"has_missing": False, "count": 3, "rate": 0.5}


def test_load_recovers_from_a_corrupt_file_rather_than_raising(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text("not valid json{{{")
    assert _checkpoint.load(str(path)) == {}
