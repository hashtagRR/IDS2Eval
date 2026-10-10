"""Structural, config-level recommendations for a run's flagged/warned checks.

Deliberately narrow: only checks with an unambiguous, mechanical fix get a
patch (a partial config to merge onto the run's own resolved_config.json).
Everything else - shortcut-feature checks (leakage_screen, one_rule_check,
feature_auc_ranking_check) chief among them - names a suspiciously
predictive feature, not a defect, and this project's own examples show why
that distinction matters: UNSW-NB15's sttl is flagged by exactly these
checks every time, but feature_category_ablation_check/artifact_sensitivity_
check show the model barely depends on it. Recommending "drop it" would be
bad advice dressed up as a fix. So the shortcut-feature family gets a
different kind of recommendation, enabling result_robustness_check, itself
just more evidence, not a change to the data. Checks that report a property
of the data or a documented fact rather than something fixable at all
(known_issue_lookup, homogeneity_test, resplit_falsification, ...) get an
explanatory note and no patch, never an invented "fix."

Every finding with status "flag" or "warning" ends up in the output, one
way or another: build_recommendations() tracks which checks a patch
already covers, and falls back to a note (a specific one from
_NOT_FIXABLE_NOTES, or a generic one if a check isn't in that table at
all) for everything else. A check silently missing from the list would
misreport "nothing to recommend" for a run that still has an unaddressed
flag - the exact bug this guarantees against.

A recommendation's "patch" is a partial config dict, deep-merged onto the
run's resolved config with config.apply_patch(); the caller (CLI or
dashboard) decides which recommendations to apply, and can edit the
resulting YAML by hand before re-running - this module only ever proposes.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ..config import apply_patch

# Checks that name a feature which is merely suspiciously predictive, not a
# defect - the "recommendation" there is more evidence, not feature removal.
_SHORTCUT_FEATURE_CHECKS = ("leakage_screen", "one_rule_check", "feature_auc_ranking_check")

# Checks that report a property of the data or a documented fact rather
# than something a config change fixes. Each gets a short explanation of
# why there's no patch, so a flagged/warned check is never silently
# omitted from the recommendation list.
_NOT_FIXABLE_NOTES = {
    "dedup_check": (
        "Reports duplication already present in the data. preprocessing.dedup "
        "(on by default) already removes it before training; if this is still "
        "flagged after dedup, see near_duplicate_class_check below instead."
    ),
    "label_conflict_check": (
        "Contradictory ground truth for identical feature vectors. Usually "
        "resolves once preprocessing.dedup runs (the conflicting rows were "
        "exact duplicates); if it persists after dedup, the contradiction is "
        "in the labels themselves, not fixable by a config change."
    ),
    "near_duplicate_class_check": (
        "Near-identical (not exact) feature vectors mapped to different "
        "labels. preprocessing.dedup only removes exact duplicates, so this "
        "can't be config-fixed; it's evidence two classes may not be "
        "reliably distinguishable in this feature set."
    ),
    "row_order_leakage_check": (
        "Rows are still in collection order. For dataset.raw_files, IDS2Eval's "
        "own split already shuffles regardless of source order, so this "
        "shouldn't happen there; for a pre-split train_file/test_file pair, "
        "the file itself is ordered and there's no config change that "
        "reshuffles it, only obtaining the combined unsplit data instead."
    ),
    "homogeneity_test": (
        "Tests whether test rows sit closer to training rows than training rows "
        "sit to each other. A property of the data, not a config problem."
    ),
    "resplit_falsification": (
        "Tests whether a session-grouped split costs accuracy. A flag here "
        "means session-correlated leakage may be doing real work; report "
        "results under the grouped split, or investigate dataset.group_columns, "
        "rather than treating it as fixable."
    ),
    "scenario_holdout_falsification": (
        "Tests whether accuracy survives never having seen an entire "
        "collection scenario. A flag means generalization to genuinely new "
        "conditions is worse than the random split suggests; not fixable by "
        "a config change, only reportable as a caveat."
    ),
    "cross_capture_matrix_check": (
        "N x N cross-scenario accuracy matrix. Asymmetric results are a "
        "property of the scenarios themselves, not something to fix."
    ),
    "class_distribution_report": (
        "Reports imbalance, it doesn't diagnose a defect. preprocessing."
        "sampling (SMOTE etc.) is a real option but a judgment call this "
        "module won't make automatically - see configs/README.md."
    ),
    "schema_fingerprint_check": (
        "Matches a documented extractor bug by column-name fingerprint. "
        "A fact about the tool that produced this data, not fixable here."
    ),
    "known_issue_lookup": (
        "A curated, published problem with this specific dataset. Disclose "
        "it when reporting results; there's nothing in your config to change."
    ),
    "result_robustness_check": (
        "Measures whether the headline accuracy is sensitive to split/dedup/"
        "feature-set methodology, it doesn't diagnose a fixable defect. A "
        "flag means the reported number moves depending on how the "
        "experiment is set up - disclose it as a caveat on the result, "
        "there's no config change that makes a model methodology-invariant."
    ),
    "feature_category_ablation_check": (
        "Reports how much accuracy a declared schema.feature_categories "
        "group costs when removed. Evidence to report, not a defect: which "
        "category the result depends on is exactly the point, dropping it "
        "automatically would defeat the purpose of measuring this."
    ),
    "artifact_sensitivity_check": (
        "Measures how much a fitted model's predictions actually depend on "
        "one column when its values are reshuffled, inside the full feature "
        "set. Like the shortcut-feature checks above, a flag here is "
        "evidence to weigh, not necessarily a defect - a model can be "
        "accurate while barely depending on the column in question."
    ),
    "synthetic_realism_check": (
        "Needs audit.reference_dataset; a flag means this dataset's rows "
        "are easily distinguished from real traffic by a domain classifier. "
        "Evidence about how representative this data is, not something a "
        "config change to this dataset fixes."
    ),
    "cross_dataset_drift_check": (
        "Needs audit.reference_dataset; a flag means accuracy drops "
        "materially on that independent dataset. Evidence about "
        "generalization, to disclose alongside the benchmark result, not "
        "fixable by a config change to this dataset."
    ),
    "seed_sensitivity_check": (
        "Re-fits leakage_screen/one_rule_check across a few seeds and flags "
        "if their flag/ok conclusion isn't stable. Means a single-seed "
        "result from those checks shouldn't be over-trusted; report the "
        "instability rather than picking a favorable seed."
    ),
}

_GENERIC_NOTE = (
    "No structural, mechanical fix for this one - see the check's own "
    "summary and details above, and guide/checks.md for what it tests."
)


def _drop_columns_recommendation(by_check: dict, cfg: dict) -> dict | None:
    candidates: dict[str, set[str]] = {}

    f = by_check.get("identity_column_flag")
    if f and f["status"] == "flag":
        for col in f["details"].get("suggested_drop", []):
            candidates.setdefault(col, set()).add("identity_column_flag")

    f = by_check.get("low_cardinality_warning")
    if f and f["status"] == "warning":
        for col in f["details"].get("flagged", []):
            candidates.setdefault(col, set()).add("low_cardinality_warning")

    f = by_check.get("port_protocol_shortcut_check")
    if f and f["status"] == "flag":
        for col in (f["details"].get("port_column"), f["details"].get("protocol_column")):
            if col:
                candidates.setdefault(col, set()).add("port_protocol_shortcut_check")

    f = by_check.get("temporal_leakage_check")
    if f and f["status"] == "flag":
        col = f["details"].get("column")
        if col:
            candidates.setdefault(col, set()).add("temporal_leakage_check")

    f = by_check.get("data_integrity_check")
    if f and f["status"] in ("flag", "warning"):
        d = f["details"]
        for col in d.get("constant_features", []):
            candidates.setdefault(col, set()).add("data_integrity_check (constant)")
        for col in d.get("missing_by_feature", {}):
            candidates.setdefault(col, set()).add("data_integrity_check (missing values)")
        for col in d.get("inf_by_feature", {}):
            candidates.setdefault(col, set()).add("data_integrity_check (+-inf values)")

    if not candidates:
        return None
    existing = set(cfg["schema"].get("drop_columns") or [])
    new_cols = sorted(c for c in candidates if c not in existing)
    if not new_cols:
        return None

    # identity_column_flag/low_cardinality_warning/port_protocol_shortcut_check/
    # flow_group_leakage_check/temporal_leakage_check all test the column
    # named in id_like_columns/flow_id_columns/timestamp_column directly
    # against the raw loaded data - none of them look at schema.drop_columns
    # at all. Adding a column to drop_columns alone would not stop the check
    # that flagged it from flagging it again on the very next run; clearing
    # the declaration here is what actually does.
    schema_patch: dict = {"drop_columns": sorted(existing | set(new_cols))}
    new_set = set(new_cols)
    remaining_id_like = [c for c in cfg["schema"].get("id_like_columns") or [] if c not in new_set]
    if remaining_id_like != (cfg["schema"].get("id_like_columns") or []):
        schema_patch["id_like_columns"] = remaining_id_like
    remaining_flow_id = [c for c in cfg["schema"].get("flow_id_columns") or [] if c not in new_set]
    if remaining_flow_id != (cfg["schema"].get("flow_id_columns") or []):
        schema_patch["flow_id_columns"] = remaining_flow_id
    if cfg["schema"].get("timestamp_column") in new_set:
        schema_patch["timestamp_column"] = None

    reasons = sorted({r for rs in candidates.values() for r in rs})
    return {
        "id": "drop_flagged_columns",
        "title": f"Add {len(new_cols)} flagged column(s) to schema.drop_columns",
        "checks": reasons,
        "explanation": (
            f"{', '.join(new_cols)} were named by: {', '.join(reasons)}. Each is "
            "either an identity-style shortcut, a timestamp tested standalone, "
            "or a column data_integrity_check found broken (constant/missing/"
            "±inf) - dropping it removes the column from training entirely, "
            "the same fix in every case. Also clears it from id_like_columns/"
            "flow_id_columns/timestamp_column where it was declared: those "
            "checks test the raw column directly and ignore drop_columns, so "
            "leaving the declaration in place would flag it again next run."
        ),
        "patch": {"schema": schema_patch},
    }


def _grouped_split_recommendation(by_check: dict, cfg: dict) -> dict | None:
    f = by_check.get("flow_group_leakage_check")
    if not f or f["status"] != "flag":
        return None
    flow_cols = f["details"].get("flow_id_columns", [])
    if not flow_cols:
        return None
    if not cfg["dataset"].get("raw_files"):
        return {
            "id": "grouped_split_unavailable", "title": "Session-grouped split isn't available",
            "checks": ["flow_group_leakage_check"],
            "explanation": (
                "The same flow identity appears on both sides of the split, but "
                "dataset.split_mode: grouped needs dataset.raw_files (it builds the "
                "split itself); this dataset uses a pre-split train_file/test_file "
                "pair, so the split can't be rebuilt without the combined raw data."
            ),
            "patch": None,
        }
    return {
        "id": "grouped_split", "title": "Switch to a session-grouped split",
        "checks": ["flow_group_leakage_check"],
        "explanation": (
            f"The same flow identity ({', '.join(flow_cols)}) appears on both sides "
            "of the split; a grouped split keeps every row sharing that identity on "
            "one side, making this specific leakage structurally impossible."
        ),
        "patch": {"dataset": {"split_mode": "grouped", "group_columns": flow_cols}},
    }


def _result_robustness_recommendation(by_check: dict, cfg: dict) -> dict | None:
    flagged = [c for c in _SHORTCUT_FEATURE_CHECKS if by_check.get(c, {}).get("status") == "flag"]
    if not flagged:
        return None
    if cfg["audit"].get("result_robustness_check"):
        return None
    if not cfg["dataset"].get("raw_files"):
        return {
            "id": "result_robustness_unavailable", "title": "result_robustness_check isn't available",
            "checks": flagged,
            "explanation": (
                f"{', '.join(flagged)} named a suspiciously predictive feature - not "
                "necessarily a defect, since a model can be accurate while barely "
                "depending on it (see guide/checks.md). result_robustness_check would "
                "measure that directly, but needs dataset.raw_files; this dataset uses "
                "a pre-split train_file/test_file pair."
            ),
            "patch": None,
        }
    return {
        "id": "enable_result_robustness", "title": "Enable result_robustness_check",
        "checks": flagged,
        "explanation": (
            f"{', '.join(flagged)} named a suspiciously predictive feature - not "
            "necessarily a defect, since a model can be accurate while barely "
            "depending on it (this project's own UNSW-NB15 example is exactly this "
            "case). Dropping the feature isn't recommended automatically; "
            "result_robustness_check measures whether the headline accuracy actually "
            "moves across split/dedup/feature-set conditions before you decide."
        ),
        "patch": {"audit": {"result_robustness_check": True}},
    }


def build_recommendations(findings: list[dict], cfg: dict) -> list[dict]:
    """findings: the run's final audit findings (the after-dedup pass if
    preprocessing.dedup ran, otherwise the only pass - the same findings the
    scorecard's verdict is judged on), each a full Finding dict including
    "details". cfg: that run's resolved config.

    Every finding with status "flag" or "warning" ends up in exactly one
    recommendation (a patch, or a note explaining why there isn't one) -
    never silently absent. A check this module doesn't specifically know
    about yet (a future check, or a v2 check not otherwise covered) still
    gets a generic fallback note rather than vanishing from the list, which
    would otherwise misleadingly report "nothing to recommend" for a run
    that still has an unaddressed flag.
    """
    by_check = {f["check"]: f for f in findings}
    recs: list[dict] = []
    covered: set[str] = set()

    for builder in (_drop_columns_recommendation, _grouped_split_recommendation,
                    _result_robustness_recommendation):
        rec = builder(by_check, cfg)
        if rec:
            recs.append(rec)
            covered.update(rec["checks"])

    # data_integrity_check's missing-label symptom is never addressed by
    # dropping columns (there's no column to drop for a missing label
    # value), so it gets its own note even when the same check's other
    # symptoms (constant/missing-feature/±inf columns) already got a patch
    # and left the check name in `covered` above.
    di = by_check.get("data_integrity_check")
    if di and di["details"].get("missing_label_count"):
        recs.append({
            "id": "note_data_integrity_check_missing_labels",
            "title": "data_integrity_check: missing label values have no automatic fix",
            "checks": ["data_integrity_check"],
            "explanation": (
                f"{di['details']['missing_label_count']} row(s) have no label value at "
                "all - not something a config change can supply. Re-collect or "
                "re-label those rows, or drop them before this dataset is loaded."
            ),
            "patch": None,
        })
        covered.add("data_integrity_check")

    for f in findings:
        if f["status"] not in ("flag", "warning") or f["check"] in covered:
            continue
        note = _NOT_FIXABLE_NOTES.get(f["check"], _GENERIC_NOTE)
        recs.append({
            "id": f"note_{f['check']}", "title": f"{f['check']}: no automatic fix",
            "checks": [f["check"]], "explanation": note, "patch": None,
        })
        covered.add(f["check"])

    return recs


def recommendations_for_run(run_dir: str | Path) -> tuple[list[dict], dict]:
    """Reads a completed run directory's own artifacts and returns
    (recommendations, resolved_config) - the same resolved_config a patch
    would be applied to.
    """
    run_dir = Path(run_dir)
    cfg = json.loads((run_dir / "resolved_config.json").read_text())
    after_path = run_dir / "audit_report_after.json"
    before_path = run_dir / "audit_report_before.json"
    if after_path.exists():
        findings = json.loads(after_path.read_text())
    elif before_path.exists():
        findings = json.loads(before_path.read_text())
    else:
        findings = []
    return build_recommendations(findings, cfg), cfg


def render_report(recommendations: list[dict]) -> str:
    if not recommendations:
        return "No flagged or warned check has a recommendation - nothing to report."
    lines = []
    for rec in recommendations:
        lines.append(f"[{rec['id']}] {rec['title']}")
        lines.append(f"  checks: {', '.join(rec['checks'])}")
        lines.append(f"  {rec['explanation']}")
        if rec["patch"]:
            patch_text = yaml.safe_dump(rec["patch"], sort_keys=False).strip()
            lines.append("  patch:")
            lines.extend(f"    {line}" for line in patch_text.splitlines())
        else:
            lines.append("  patch: none (see explanation above)")
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def apply_recommendations(cfg: dict, recommendations: list[dict], ids: list[str]) -> dict:
    """Merges the patches of the recommendations whose id is in `ids` onto
    cfg, in the order given. Recommendations with patch=None (informational
    only) are silently skipped even if their id is passed.
    """
    by_id = {r["id"]: r for r in recommendations}
    patched = cfg
    for rec_id in ids:
        rec = by_id.get(rec_id)
        if rec and rec.get("patch"):
            patched = apply_patch(patched, rec["patch"])
    return patched
