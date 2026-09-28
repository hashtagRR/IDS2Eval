from ids2eval.reporting.intervention_manifest import build_manifest


def _finding(check, status, details=None):
    return {"check": check, "status": status, "summary": "irrelevant here", "details": details or {}}


def test_build_manifest_ignores_findings_that_are_not_interventions():
    findings = [_finding("dedup_check", "flag"), _finding("known_issue_lookup", "warning")]
    assert build_manifest(findings) == []


def test_build_manifest_excludes_a_no_op_intervention_check():
    # Reproduced live: scenario_holdout_falsification with no schema.scenario_column
    # configured returns status "ok" with empty details - a no-op, not a performed
    # intervention. Every INTERVENTION_CHECKS check follows this same "details: {}"
    # no-op convention, so this must be excluded, not reported as performed: true.
    findings = [_finding("scenario_holdout_falsification", "ok", {})]
    assert build_manifest(findings) == []


def test_build_manifest_includes_every_intervention_check_present():
    findings = [
        _finding("resplit_falsification", "ok", {"random_accuracy": 0.99, "grouped_accuracy": 0.98, "drop": 0.01}),
        _finding("dedup_check", "flag"),  # not an intervention, should be excluded
    ]
    manifest = build_manifest(findings)
    assert len(manifest) == 1
    assert manifest[0]["finding"]["check"] == "resplit_falsification"


def test_build_manifest_record_has_all_four_sections():
    findings = [_finding("resplit_falsification", "flag", {"drop": 0.05})]
    record = build_manifest(findings)[0]
    assert set(record) == {"finding", "intervention", "consequence", "conclusion"}
    assert record["finding"]["evidence"] == {"drop": 0.05}
    assert record["consequence"] == {"drop": 0.05}
    assert record["intervention"]["performed"] is True
    assert record["intervention"]["type"] == "resplit_falsification"


def test_build_manifest_conclusion_uses_explicit_material_field_when_present():
    findings = [_finding("repeated_seed_falsification_check", "ok", {"material": False})]
    assert build_manifest(findings)[0]["conclusion"]["status"] == "investigated_not_material"

    findings = [_finding("repeated_seed_falsification_check", "flag", {"material": True})]
    assert build_manifest(findings)[0]["conclusion"]["status"] == "material"

    findings = [_finding("repeated_seed_falsification_check", "warning", {"material": None})]
    assert build_manifest(findings)[0]["conclusion"]["status"] == "inconclusive"


def test_build_manifest_conclusion_falls_back_to_status_when_no_material_field():
    # feature_category_ablation_check has no explicit `material` field - falls back to
    # its ok/warning/flag status. Non-empty details on every case: a real finding this
    # check reports always carries at least a baseline_accuracy, never truly empty -
    # only the no-op path returns {}, covered separately above.
    details = {"baseline_accuracy": 0.9}
    assert build_manifest([_finding("feature_category_ablation_check", "flag", details)])[0][
        "conclusion"]["status"] == "material"
    assert build_manifest([_finding("feature_category_ablation_check", "ok", details)])[0][
        "conclusion"]["status"] == "investigated_not_material"
    assert build_manifest([_finding("feature_category_ablation_check", "warning", details)])[0][
        "conclusion"]["status"] == "inconclusive"
