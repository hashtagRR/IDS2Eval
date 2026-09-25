import json

from ids2eval.reporting import drift


def _write_scorecard(run_dir, overall_status, checks, train_hash="abc", test_hash="def"):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "scorecard.json").write_text(json.dumps({
        "overall_status": overall_status,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "checks": checks,
        "dataset_fingerprint": {"train_content_hash": train_hash, "test_content_hash": test_hash},
    }))


def _check_row(check, status):
    return {"check": check, "category": "audit", "before": {"status": status, "summary": "s"}, "after": None}


def test_find_previous_run_picks_the_latest_run_with_a_scorecard(tmp_path):
    output_dir = tmp_path / "output"
    for name in ("2026-01-01_000000_000000", "2026-01-02_000000_000000", "2026-01-03_000000_000000"):
        (output_dir / "runs" / name).mkdir(parents=True)
    _write_scorecard(output_dir / "runs" / "2026-01-01_000000_000000", "passed", [])
    _write_scorecard(output_dir / "runs" / "2026-01-02_000000_000000", "passed", [])
    # 2026-01-03 has no scorecard.json (e.g. a run that failed before reaching it) - skipped
    current = output_dir / "runs" / "2026-01-04_000000_000000"
    current.mkdir(parents=True)
    _write_scorecard(current, "passed", [])

    previous = drift.find_previous_run(output_dir, current)
    assert previous.name == "2026-01-02_000000_000000"


def test_find_previous_run_none_when_no_output_dir_or_no_prior_runs(tmp_path):
    assert drift.find_previous_run(tmp_path / "does-not-exist", tmp_path / "current") is None
    output_dir = tmp_path / "output"
    current = output_dir / "runs" / "only-run"
    current.mkdir(parents=True)
    _write_scorecard(current, "passed", [])
    assert drift.find_previous_run(output_dir, current) is None


def test_compare_detects_a_check_that_regressed(tmp_path):
    previous_dir = tmp_path / "previous"
    _write_scorecard(previous_dir, "passed", [_check_row("dedup_check", "ok")])
    current = {
        "overall_status": "failed",
        "checks": [_check_row("dedup_check", "flag")],
        "dataset_fingerprint": {"train_content_hash": "abc", "test_content_hash": "def"},
    }
    result = drift.compare(current, previous_dir)
    assert result["changed_checks"] == [{"check": "dedup_check", "previous_status": "ok", "current_status": "flag"}]
    assert result["fingerprint_changed"] is False


def test_compare_reports_no_changes_when_every_check_matches(tmp_path):
    previous_dir = tmp_path / "previous"
    _write_scorecard(previous_dir, "passed", [_check_row("dedup_check", "ok")])
    current = {
        "overall_status": "passed",
        "checks": [_check_row("dedup_check", "ok")],
        "dataset_fingerprint": {"train_content_hash": "abc", "test_content_hash": "def"},
    }
    result = drift.compare(current, previous_dir)
    assert result["changed_checks"] == []


def test_compare_flags_a_different_dataset_via_content_hash(tmp_path):
    previous_dir = tmp_path / "previous"
    _write_scorecard(previous_dir, "passed", [], train_hash="abc")
    current = {
        "overall_status": "passed", "checks": [],
        "dataset_fingerprint": {"train_content_hash": "different", "test_content_hash": "def"},
    }
    result = drift.compare(current, previous_dir)
    assert result["fingerprint_changed"] is True


def test_compare_returns_none_when_previous_scorecard_is_unreadable(tmp_path):
    previous_dir = tmp_path / "previous"
    previous_dir.mkdir(parents=True)
    (previous_dir / "scorecard.json").write_text("not json")
    current = {"overall_status": "passed", "checks": [],
               "dataset_fingerprint": {"train_content_hash": "a", "test_content_hash": "b"}}
    assert drift.compare(current, previous_dir) is None
