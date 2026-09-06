from ids2eval import scorecard


def _finding(check, status, summary="a summary"):
    return {"check": check, "status": status, "summary": summary, "details": {}}


def _fingerprint():
    return {
        "train_rows": 100, "test_rows": 20,
        "train_content_hash": "abc123", "test_content_hash": "def456",
    }


def test_all_ok_findings_pass(base_cfg):
    findings = [_finding("dedup_check", "ok"), _finding("leakage_screen", "ok")]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    assert sc["overall_status"] == "passed"


def test_a_warning_with_no_flags_passes_with_warnings(base_cfg):
    findings = [_finding("dedup_check", "ok"), _finding("class_distribution_report", "warning")]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    assert sc["overall_status"] == "passed_with_warnings"


def test_any_flag_fails_regardless_of_other_statuses(base_cfg):
    findings = [
        _finding("dedup_check", "ok"),
        _finding("class_distribution_report", "warning"),
        _finding("leakage_screen", "flag"),
    ]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    assert sc["overall_status"] == "failed"


def test_no_findings_defaults_to_passed(base_cfg):
    sc = scorecard.build_scorecard([], "before", base_cfg, _fingerprint())
    assert sc["overall_status"] == "passed"


def test_scorecard_carries_version_and_fingerprint_info(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "ok")], "after", base_cfg, _fingerprint())
    assert sc["scorecard_schema_version"] == "1.0"
    assert sc["dataset_name"] == base_cfg["dataset"]["name"]
    assert sc["dataset_fingerprint"]["train_content_hash"] == "abc123"
    assert "ids2eval_version" in sc
    assert sc["audit_stage"] == "after"


def test_findings_in_scorecard_omit_details(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "flag")], "after", base_cfg, _fingerprint())
    assert "details" not in sc["findings"][0]
    assert sc["findings"][0] == {"check": "dedup_check", "status": "flag", "summary": "a summary"}


def test_render_markdown_includes_verdict_and_every_check(base_cfg):
    findings = [_finding("dedup_check", "ok"), _finding("leakage_screen", "flag", "leak found")]
    sc = scorecard.build_scorecard(findings, "after", base_cfg, _fingerprint())
    md = scorecard.render_markdown(sc)
    assert "Failed" in md
    assert "dedup_check" in md
    assert "leakage_screen" in md
    assert "leak found" in md
    assert "Citing this result" in md
    assert "arxiv.org/abs/1803.09010" in md


def test_render_markdown_omits_plot_image_by_default(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "ok")], "after", base_cfg, _fingerprint())
    md = scorecard.render_markdown(sc)
    assert "scorecard.png" not in md


def test_render_markdown_embeds_plot_image_when_has_plot(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "ok")], "after", base_cfg, _fingerprint())
    md = scorecard.render_markdown(sc, has_plot=True)
    assert "![IDS2Eval Scorecard](scorecard.png)" in md
    assert "scorecard.pdf" in md  # mentioned as the citable vector figure
