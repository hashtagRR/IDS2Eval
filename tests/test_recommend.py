import json

from ids2eval.config import validate_config
from ids2eval.reporting.recommend import (
    _GENERIC_NOTE,
    apply_recommendations,
    build_recommendations,
    recommendations_for_run,
)


def _finding(check, status, details=None, summary="s"):
    return {"check": check, "status": status, "summary": summary, "details": details or {}}


def _by_id(recs):
    return {r["id"]: r for r in recs}


def test_no_recommendations_when_everything_is_ok(base_cfg):
    findings = [_finding("dedup_check", "ok"), _finding("leakage_screen", "ok")]
    assert build_recommendations(findings, base_cfg) == []


def test_drop_columns_recommendation_merges_across_checks(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    findings = [
        _finding("identity_column_flag", "flag", {"suggested_drop": ["SrcIP"]}),
        _finding("port_protocol_shortcut_check", "flag", {"port_column": "SrcIP", "protocol_column": "Proto"}),
        _finding("temporal_leakage_check", "flag", {"column": "Timestamp"}),
        _finding("data_integrity_check", "warning", {
            "constant_features": ["Const1"], "missing_by_feature": {"Miss1": 5}, "inf_by_feature": {},
        }),
    ]
    recs = build_recommendations(findings, base_cfg)
    rec = _by_id(recs)["drop_flagged_columns"]
    assert rec["patch"] == {"schema": {"drop_columns": sorted(["SrcIP", "Proto", "Timestamp", "Const1", "Miss1"])}}
    # SrcIP named by two checks, only appears once in the patch and both checks are credited
    assert "identity_column_flag" in rec["checks"]
    assert "port_protocol_shortcut_check" in rec["checks"]


def test_drop_columns_recommendation_clears_the_column_from_id_like_columns(base_cfg):
    # identity_column_flag/port_protocol_shortcut_check/flow_group_leakage_check/
    # temporal_leakage_check test the raw declared column directly and ignore
    # drop_columns entirely, so leaving the declaration in place would flag it
    # again next run even after it's dropped.
    base_cfg["schema"]["id_like_columns"] = ["SrcIP", "DstIP"]
    findings = [_finding("identity_column_flag", "flag", {"suggested_drop": ["SrcIP"]})]
    rec = _by_id(build_recommendations(findings, base_cfg))["drop_flagged_columns"]
    assert rec["patch"]["schema"]["id_like_columns"] == ["DstIP"]


def test_drop_columns_recommendation_clears_timestamp_column_if_dropped(base_cfg):
    base_cfg["schema"]["timestamp_column"] = "Timestamp"
    findings = [_finding("temporal_leakage_check", "flag", {"column": "Timestamp"})]
    rec = _by_id(build_recommendations(findings, base_cfg))["drop_flagged_columns"]
    assert rec["patch"]["schema"]["timestamp_column"] is None


def test_drop_columns_recommendation_returns_none_once_the_check_itself_clears(base_cfg):
    # The realistic downstream state after a previous drop_flagged_columns
    # patch: the column is in drop_columns AND cleared from id_like_columns,
    # so the check itself no longer flags at all.
    base_cfg["schema"]["drop_columns"] = ["SrcIP"]
    findings = [_finding("identity_column_flag", "ok")]
    assert build_recommendations(findings, base_cfg) == []


def test_a_check_still_flagging_an_already_dropped_column_falls_back_to_a_note(base_cfg):
    # id_like_columns wasn't cleared (e.g. a hand-edited config): the check
    # still tests the raw column directly and flags it again. No new
    # column-drop patch is possible (it's already dropped), so this must not
    # silently vanish from the report - the exact bug this guards against.
    base_cfg["schema"]["drop_columns"] = ["SrcIP"]
    findings = [_finding("identity_column_flag", "flag", {"suggested_drop": ["SrcIP"]})]
    rec = _by_id(build_recommendations(findings, base_cfg))["note_identity_column_flag"]
    assert rec["patch"] is None


def test_low_cardinality_warning_only_triggers_drop_columns_at_warning_status(base_cfg):
    findings = [_finding("low_cardinality_warning", "warning", {"flagged": ["SrcIP"]})]
    rec = _by_id(build_recommendations(findings, base_cfg))["drop_flagged_columns"]
    assert rec["patch"]["schema"]["drop_columns"] == ["SrcIP"]


def test_grouped_split_recommendation_when_raw_files_available(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    findings = [_finding("flow_group_leakage_check", "flag", {"flow_id_columns": ["SrcIP", "DstIP"]})]
    rec = _by_id(build_recommendations(findings, base_cfg))["grouped_split"]
    assert rec["patch"] == {"dataset": {"split_mode": "grouped", "group_columns": ["SrcIP", "DstIP"]}}


def test_grouped_split_recommendation_unavailable_for_pre_split_pair(base_cfg):
    base_cfg["dataset"]["raw_files"] = []
    base_cfg["dataset"]["train_file"] = "train.csv"
    base_cfg["dataset"]["test_file"] = "test.csv"
    findings = [_finding("flow_group_leakage_check", "flag", {"flow_id_columns": ["SrcIP"]})]
    rec = _by_id(build_recommendations(findings, base_cfg))["grouped_split_unavailable"]
    assert rec["patch"] is None


def test_result_robustness_recommendation_for_shortcut_feature_checks(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    findings = [_finding("leakage_screen", "flag"), _finding("one_rule_check", "ok")]
    rec = _by_id(build_recommendations(findings, base_cfg))["enable_result_robustness"]
    assert rec["patch"] == {"audit": {"result_robustness_check": True}}
    assert rec["checks"] == ["leakage_screen"]


def test_result_robustness_recommendation_skipped_if_already_enabled(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["result_robustness_check"] = True
    findings = [_finding("leakage_screen", "flag")]
    assert "enable_result_robustness" not in _by_id(build_recommendations(findings, base_cfg))


def test_result_robustness_recommendation_unavailable_for_pre_split_pair(base_cfg):
    base_cfg["dataset"]["train_file"] = "train.csv"
    base_cfg["dataset"]["test_file"] = "test.csv"
    findings = [_finding("feature_auc_ranking_check", "flag")]
    rec = _by_id(build_recommendations(findings, base_cfg))["result_robustness_unavailable"]
    assert rec["patch"] is None


def test_not_fixable_checks_get_a_note_with_no_patch(base_cfg):
    findings = [_finding("known_issue_lookup", "warning"), _finding("homogeneity_test", "flag")]
    recs = _by_id(build_recommendations(findings, base_cfg))
    assert recs["note_known_issue_lookup"]["patch"] is None
    assert recs["note_homogeneity_test"]["patch"] is None


def test_ok_status_checks_never_get_a_note(base_cfg):
    findings = [_finding("known_issue_lookup", "ok")]
    assert build_recommendations(findings, base_cfg) == []


def test_every_new_v2_evidence_check_gets_its_own_specific_note(base_cfg):
    # result_robustness_check itself flagging (after being enabled by an
    # earlier recommendation) is exactly the reported bug: it produced no
    # recommendation at all, so a still-failed re-run looked like nothing
    # was wrong. Same coverage gap existed for these other v2 checks.
    for check in ("result_robustness_check", "feature_category_ablation_check",
                  "artifact_sensitivity_check", "synthetic_realism_check",
                  "cross_dataset_drift_check", "seed_sensitivity_check"):
        findings = [_finding(check, "flag")]
        rec = _by_id(build_recommendations(findings, base_cfg))[f"note_{check}"]
        assert rec["patch"] is None
        assert rec["explanation"] != _GENERIC_NOTE  # each has its own specific wording


def test_an_unknown_check_falls_back_to_the_generic_note_instead_of_vanishing(base_cfg):
    findings = [_finding("some_future_check_this_module_has_never_heard_of", "flag")]
    rec = _by_id(build_recommendations(findings, base_cfg))["note_some_future_check_this_module_has_never_heard_of"]
    assert rec["patch"] is None
    assert rec["explanation"] == _GENERIC_NOTE


def test_missing_label_values_get_their_own_note_even_when_other_symptoms_are_patched(base_cfg):
    findings = [_finding("data_integrity_check", "flag", {
        "missing_label_count": 3, "constant_features": ["Const1"],
        "missing_by_feature": {}, "inf_by_feature": {},
    })]
    recs = _by_id(build_recommendations(findings, base_cfg))
    assert recs["drop_flagged_columns"]["patch"]["schema"]["drop_columns"] == ["Const1"]
    assert recs["note_data_integrity_check_missing_labels"]["patch"] is None
    assert "3 row(s)" in recs["note_data_integrity_check_missing_labels"]["explanation"]
    # the check name is fully covered - no separate generic fallback note too
    assert "note_data_integrity_check" not in recs


def test_apply_recommendations_merges_selected_patches_onto_config(base_cfg):
    base_cfg["dataset"]["raw_files"] = ["a.csv"]
    base_cfg["audit"]["resplit_falsification"] = False
    findings = [
        _finding("identity_column_flag", "flag", {"suggested_drop": ["SrcIP"]}),
        _finding("leakage_screen", "flag"),
    ]
    recs = build_recommendations(findings, base_cfg)
    patched = apply_recommendations(base_cfg, recs, ["drop_flagged_columns", "enable_result_robustness"])
    assert patched["schema"]["drop_columns"] == ["SrcIP"]
    assert patched["audit"]["result_robustness_check"] is True
    validate_config(patched)  # the patched config must still be a valid config


def test_apply_recommendations_ignores_unknown_or_unpatched_ids(base_cfg):
    findings = [_finding("known_issue_lookup", "warning")]
    recs = build_recommendations(findings, base_cfg)
    patched = apply_recommendations(base_cfg, recs, ["note_known_issue_lookup", "no-such-id"])
    assert patched == base_cfg


def test_recommendations_for_run_reads_a_real_run_directory(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    cfg = {"dataset": {"raw_files": ["a.csv"]}, "schema": {"drop_columns": []}, "audit": {}}
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg))
    findings = [_finding("identity_column_flag", "flag", {"suggested_drop": ["SrcIP"]})]
    (run_dir / "audit_report_after.json").write_text(json.dumps(findings))
    recs, loaded_cfg = recommendations_for_run(run_dir)
    assert loaded_cfg == cfg
    assert _by_id(recs)["drop_flagged_columns"]["patch"]["schema"]["drop_columns"] == ["SrcIP"]


def test_recommendations_for_run_falls_back_to_the_before_pass_without_dedup(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    cfg = {"dataset": {}, "schema": {"drop_columns": []}, "audit": {}}
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg))
    findings = [_finding("known_issue_lookup", "warning")]
    (run_dir / "audit_report_before.json").write_text(json.dumps(findings))
    recs, _ = recommendations_for_run(run_dir)
    assert _by_id(recs)["note_known_issue_lookup"]
