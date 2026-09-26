import json

import pytest

from ids2eval.reporting import cite


def _scorecard():
    return {
        "dataset_name": "unsw-nb15",
        "ids2eval_version": "0.1.0",
        "ids2eval_git_commit": "abc1234def",
        "scorecard_schema_version": "1.2",
        "overall_status": "passed_with_warnings",
        "generated_at": "2026-09-26T12:00:00+00:00",
        "dataset_fingerprint": {"train_content_hash": "aaaaaaaa1111", "test_content_hash": "bbbbbbbb2222"},
    }


def test_citation_bibtex_key_is_derived_from_dataset_and_hash():
    bib = cite.citation_bibtex(_scorecard())
    assert bib.startswith("@misc{ids2eval_unsw_nb15_aaaaaaaa,")


def test_citation_bibtex_carries_version_commit_and_verdict():
    bib = cite.citation_bibtex(_scorecard())
    assert "IDS2Eval v0.1.0" in bib
    assert "schema 1.2" in bib
    assert "abc1234def" in bib
    assert "passed with warnings" in bib
    assert "aaaaaaaa1111" in bib
    assert "bbbbbbbb2222" in bib


def test_citation_bibtex_handles_a_missing_git_commit():
    sc = _scorecard()
    sc["ids2eval_git_commit"] = None
    bib = cite.citation_bibtex(sc)
    assert "commit unknown" in bib


def test_load_scorecard_accepts_a_run_directory(tmp_path):
    (tmp_path / "scorecard.json").write_text(json.dumps(_scorecard()))
    sc = cite.load_scorecard(tmp_path)
    assert sc["dataset_name"] == "unsw-nb15"


def test_load_scorecard_accepts_a_direct_file_path(tmp_path):
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(_scorecard()))
    sc = cite.load_scorecard(path)
    assert sc["dataset_name"] == "unsw-nb15"


def test_load_scorecard_raises_a_clear_error_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="No scorecard\\.json"):
        cite.load_scorecard(tmp_path / "does-not-exist")
