from ids2eval.reporting import scorecard


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
    assert sc["scorecard_schema_version"] == "1.1"
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
    assert 'src="scorecard.png"' in md
    assert 'width="760"' in md  # explicit display width - not full native size
    assert "scorecard.pdf" in md  # mentioned as the citable vector figure


def _dedup_finding(status, dropped):
    f = _finding("dedup_check", status, f"{dropped} dropped")
    f["details"] = {
        "train_rows_raw": 100, "train_rows_deduped": 100 - dropped, "train_duplicates_dropped": dropped,
        "test_rows_raw": 20, "test_rows_deduped": 18, "test_leakage_dropped": 1, "test_duplicates_dropped": 1,
    }
    return f


def test_verdict_is_judged_on_final_findings_not_before(base_cfg):
    before = [_dedup_finding("flag", 40)]
    after = [_dedup_finding("ok", 0)]
    sc = scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before)
    assert sc["overall_status"] == "passed"
    assert sc["counts"] == {"ok": 1, "warning": 0, "flag": 0}


def test_each_check_is_one_row_with_both_passes_side_by_side(base_cfg):
    before = [_dedup_finding("flag", 40), _finding("leakage_screen", "ok", "top1=17.8%")]
    after = [_dedup_finding("ok", 0), _finding("leakage_screen", "ok", "top1=15.5%")]
    sc = scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before)
    assert [(r["check"], r["before"]["status"], r["after"]["status"]) for r in sc["checks"]] == [
        ("dedup_check", "flag", "ok"),
        ("leakage_screen", "ok", "ok"),
    ]
    assert sc["checks"][1]["before"]["summary"] == "top1=17.8%"
    assert sc["checks"][1]["after"]["summary"] == "top1=15.5%"


def test_a_check_missing_from_one_pass_gets_null_on_that_side(base_cfg):
    before = [_finding("dedup_check", "ok")]
    sc = scorecard.build_scorecard([], "after", base_cfg, _fingerprint(), findings_before=before)
    assert sc["checks"] == [{"check": "dedup_check", "category": "audit",
                             "before": {"status": "ok", "summary": "a summary"}, "after": None}]
    assert "n/a" in scorecard.render_markdown(sc)


def test_dedup_effect_only_reported_when_dedup_ran(base_cfg):
    before = [_dedup_finding("flag", 40)]
    sc = scorecard.build_scorecard([_dedup_finding("ok", 0)], "after", base_cfg, _fingerprint(), findings_before=before)
    assert sc["dedup_effect"]["train_rows_deduped"] == 60
    sc_no_dedup = scorecard.build_scorecard(before, "before", base_cfg, _fingerprint())
    assert sc_no_dedup["dedup_effect"] is None
    assert all(r["after"] is None for r in sc_no_dedup["checks"])


def test_render_markdown_has_before_and_after_columns_only_when_dedup_ran(base_cfg):
    before = [_dedup_finding("flag", 40)]
    sc = scorecard.build_scorecard([_dedup_finding("ok", 0)], "after", base_cfg, _fingerprint(), findings_before=before)
    md = scorecard.render_markdown(sc)
    assert "| Check | Raw data | Cleaned data | Summary |" in md
    assert "| `dedup_check` | 🚩 flag | ✅ pass |" in md
    assert "What cleaning removed" in md
    md_no_dedup = scorecard.render_markdown(scorecard.build_scorecard(before, "before", base_cfg, _fingerprint()))
    assert "| Check | Status | Summary |" in md_no_dedup


def test_render_html_highlights_only_rows_whose_status_changed(base_cfg):
    before = [_dedup_finding("flag", 40), _finding("leakage_screen", "ok", "x")]
    after = [_dedup_finding("ok", 0), _finding("leakage_screen", "ok", "y")]
    page = scorecard.render_html(
        scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before))
    assert page.count('<tr class="moved">') == 1
    assert "<th>Raw data</th><th>Cleaned data</th>" in page


def test_render_html_is_standalone_and_escapes_summaries(base_cfg):
    findings = [_finding("leakage_screen", "flag", "<script>alert(1)</script>")]
    sc = scorecard.build_scorecard(findings, "before", base_cfg, _fingerprint())
    page = scorecard.render_html(sc)
    assert page.startswith("<!doctype html>")
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "leakage_screen" in page
    assert "Failed" in page
    assert "http" not in page.split("<body")[0]  # no external assets in <head>


def test_renderers_accept_a_schema_1_0_scorecard(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "ok")], "after", base_cfg, _fingerprint())
    for key in ("counts", "checks", "dedup_effect"):
        del sc[key]
    assert "dedup_check" in scorecard.render_markdown(sc)
    assert "dedup_check" in scorecard.render_html(sc)


def test_render_html_shows_before_summary_on_collapsed_rows(base_cfg):
    before = [_finding("class_distribution_report", "ok", "ratio 2:1")]
    after = [_finding("class_distribution_report", "ok", "ratio 1:1")]
    sc = scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before)
    assert "raw data: ratio 2:1" in scorecard.render_html(sc)
    assert "*raw data:* ratio 2:1" in scorecard.render_markdown(sc)


def test_render_html_explains_each_known_check_on_hover(base_cfg):
    findings = [_finding("dedup_check", "ok"), _finding("some_future_check", "ok")]
    page = scorecard.render_html(scorecard.build_scorecard(findings, "before", base_cfg, _fingerprint()))
    assert page.count('class="tip"') == 1  # an unknown check gets no explainer, not a broken one
    assert scorecard.CHECK_INFO["dedup_check"][0] in page
    assert "Flag: any test row matches a train row." in page
    assert 'aria-describedby="tip-1"' in page and 'id="tip-1"' in page  # 1-based row numbering
    assert "<script" not in page


def test_every_audit_check_has_an_explainer():
    import inspect

    from ids2eval.audit import run_audit

    source = inspect.getsource(run_audit)
    checks = set(__import__("re").findall(r'audit_cfg\["(\w+)"\]', source))
    assert checks == set(scorecard.CHECK_INFO)


def test_known_issue_checks_get_their_own_single_status_section(base_cfg):
    before = [_finding("known_issue_lookup", "warning", "the actual issue text (Some et al. 2020)")]
    after = list(before)  # cli.py reuses the before-pass finding verbatim for structural checks
    sc = scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before)
    assert scorecard._rows(sc)[0]["category"] == "known_issue"

    page = scorecard.render_html(sc)
    assert "<h2>Known issues</h2>" in page
    known_section = page.split("<h2>Known issues</h2>")[1]
    assert 'colspan="2"' not in known_section  # a single Status column, never raw/cleaned
    assert known_section.count('class="badge b-warning"') == 1
    assert "the actual issue text (Some et al. 2020)" in known_section
    # and it must NOT also appear in the main Checks table
    checks_section = page.split("<h2 class=\"first\">Checks</h2>")[1].split("<h2>Known issues</h2>")[0]
    assert "known_issue_lookup" not in checks_section

    md = scorecard.render_markdown(sc)
    assert "## Known issues" in md
    known_md = md.split("## Known issues")[1]
    assert "| 1 | `known_issue_lookup` | ⚠️ warn | the actual issue text (Some et al. 2020) |" in known_md


def test_resplit_falsification_merges_into_one_cell_within_the_checks_table(base_cfg):
    # resplit_falsification is structural (same result regardless of dedup) but stays an
    # audit check, since switching dataset.split_mode can actually change its result.
    before = [_finding("resplit_falsification", "flag")]
    after = list(before)
    sc = scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before)
    assert scorecard._rows(sc)[0]["category"] == "audit"
    assert scorecard._rows(sc)[0]["structural"] is True

    page = scorecard.render_html(sc)
    checks_section = page.split("<h2 class=\"first\">Checks</h2>")[1].split("<h2>Known issues</h2>")[0] \
        if "<h2>Known issues</h2>" in page else page.split("<h2 class=\"first\">Checks</h2>")[1]
    assert 'colspan="2"' in checks_section
    assert "same on raw and cleaned data" in checks_section
    assert checks_section.count('class="badge b-flag"') == 1  # one badge, not a duplicated pair


def test_non_structural_checks_still_get_two_independent_badges(base_cfg):
    before = [_finding("dedup_check", "flag")]
    after = [_finding("dedup_check", "ok")]
    sc = scorecard.build_scorecard(after, "after", base_cfg, _fingerprint(), findings_before=before)
    assert scorecard._rows(sc)[0]["structural"] is False
    page = scorecard.render_html(sc)
    body = page.split("<tbody>")[1].split("</tbody>")[0]
    assert 'colspan="2"' not in body
    assert body.count("badge b-") == 2


def test_rows_are_numbered_starting_at_one_in_each_table(base_cfg):
    before = [_finding("dedup_check", "ok"), _finding("leakage_screen", "ok"), _finding("known_issue_lookup", "ok")]
    sc = scorecard.build_scorecard(before, "before", base_cfg, _fingerprint())
    page = scorecard.render_html(sc)
    assert '<td class="num">1</td>' in page and '<td class="num">2</td>' in page
    # the known-issue table restarts numbering at 1 too, not continuing from the checks table
    known_section = page.split("<h2>Known issues</h2>")[1]
    assert '<td class="num">1</td>' in known_section
    md = scorecard.render_markdown(sc)
    assert "| 1 | `dedup_check`" in md and "| 2 | `leakage_screen`" in md
    assert "| 1 | `known_issue_lookup`" in md


def test_known_issue_lookup_summary_names_the_actual_issue():
    # A count alone ("1 known issue(s)") tells the reader nothing they can act on.
    from ids2eval.audit import known_issues

    result = known_issues.check(None, {"dataset": {"name": "cic-ids2018"}})
    assert "Brute-Force-Web" in result["summary"]
    assert "Liu et al. 2022" in result["summary"]


def test_render_shows_previous_run_comparison_when_present(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "flag")], "before", base_cfg, _fingerprint())
    sc["previous_run_comparison"] = {
        "previous_run": "2026-01-01_000000_000000",
        "previous_generated_at": "2026-01-01T00:00:00+00:00",
        "previous_verdict": "passed",
        "fingerprint_changed": False,
        "changed_checks": [{"check": "dedup_check", "previous_status": "ok", "current_status": "flag"}],
    }
    md = scorecard.render_markdown(sc)
    assert "## Compared to the previous run" in md
    assert "2026-01-01_000000_000000" in md
    assert "`dedup_check`: ok to flag" in md

    page = scorecard.render_html(sc)
    assert "<h2>Compared to the previous run</h2>" in page
    assert "ok to flag" in page


def test_render_omits_previous_run_section_when_absent(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "ok")], "before", base_cfg, _fingerprint())
    assert "Compared to the previous run" not in scorecard.render_markdown(sc)
    assert "Compared to the previous run" not in scorecard.render_html(sc)


def test_render_notes_a_changed_dataset_fingerprint(base_cfg):
    sc = scorecard.build_scorecard([_finding("dedup_check", "ok")], "before", base_cfg, _fingerprint())
    sc["previous_run_comparison"] = {
        "previous_run": "run-1", "previous_generated_at": "2026-01-01T00:00:00+00:00",
        "previous_verdict": "passed", "fingerprint_changed": True, "changed_checks": [],
    }
    md = scorecard.render_markdown(sc)
    assert "different content hash" in md
    page = scorecard.render_html(sc)
    assert "different content hash" in page
