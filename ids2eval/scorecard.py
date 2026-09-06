"""Formalizes audit findings into a citable pass/fail scorecard.

Not a new check — a rollup of the audit findings, dataset fingerprint, and
tool version already computed elsewhere, into one stable, versioned artifact
a paper can point to (e.g. "this result was obtained on a dataset that
passed the following IDS2Eval checks"). See AUDIT_CHECKS.md's "The
scorecard" section for the prior art this format draws on.

SCHEMA_VERSION is independent of ids2eval's own package version: it only
changes if this dict's shape changes, so a citation naming a schema version
stays parseable even after ids2eval itself moves on.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import version_info

SCHEMA_VERSION = "1.0"

_STATUS_RANK = {"ok": 0, "warning": 1, "flag": 2}
_OVERALL_STATUS = {"ok": "passed", "warning": "passed_with_warnings", "flag": "failed"}
_STATUS_EMOJI = {"ok": "✅", "warning": "⚠️", "flag": "🚩"}
_VERDICT_LABEL = {
    "passed": "✅ Passed",
    "passed_with_warnings": "⚠️ Passed with warnings",
    "failed": "❌ Failed",
}


def build_scorecard(findings: list[dict], audit_stage: str, cfg: dict, fingerprint: dict) -> dict:
    """audit_stage is "before" or "after" - which of
    audit_report_before.json/audit_report_after.json these findings came
    from (whichever is the FINAL state of the data shipped in this run:
    "after" if preprocessing.dedup ran, else "before").
    """
    worst = max((f["status"] for f in findings), key=lambda s: _STATUS_RANK[s], default="ok")
    version = version_info.get_version_info()

    return {
        "scorecard_schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_name": cfg["dataset"]["name"],
        "ids2eval_version": version["version"],
        "ids2eval_git_commit": version["git_commit"],
        "audit_stage": audit_stage,
        "overall_status": _OVERALL_STATUS[worst],
        "findings": [{"check": f["check"], "status": f["status"], "summary": f["summary"]} for f in findings],
        "dataset_fingerprint": {
            "train_rows": fingerprint["train_rows"],
            "test_rows": fingerprint["test_rows"],
            "train_content_hash": fingerprint["train_content_hash"],
            "test_content_hash": fingerprint["test_content_hash"],
        },
    }


def render_markdown(scorecard: dict) -> str:
    counts = {"ok": 0, "warning": 0, "flag": 0}
    for f in scorecard["findings"]:
        counts[f["status"]] += 1

    lines = [
        "# IDS2Eval Scorecard",
        "",
        f"**Dataset:** {scorecard['dataset_name']}",
        f"**Overall status:** {_VERDICT_LABEL[scorecard['overall_status']]}",
        f"**Generated:** {scorecard['generated_at']}",
        f"**IDS2Eval version:** {scorecard['ids2eval_version']}"
        + (f" (git {scorecard['ids2eval_git_commit'][:7]})" if scorecard["ids2eval_git_commit"] else ""),
        f"**Scorecard schema version:** {scorecard['scorecard_schema_version']}",
        f"**Audit stage:** {scorecard['audit_stage']} dedup",
        "",
        "## Checks",
        "",
        "| Check | Status | Summary |",
        "|---|---|---|",
    ]
    for f in scorecard["findings"]:
        lines.append(f"| `{f['check']}` | {_STATUS_EMOJI[f['status']]} {f['status']} | {f['summary']} |")

    lines += [
        "",
        "## Citing this result",
        "",
        f"> This result was obtained on a dataset audited with IDS2Eval "
        f"v{scorecard['ids2eval_version']} (scorecard schema "
        f"{scorecard['scorecard_schema_version']}), which reported "
        f"**{scorecard['overall_status'].replace('_', ' ')}** — "
        f"{counts['ok']} ok, {counts['warning']} warning(s), {counts['flag']} flag(s) "
        f"across {len(scorecard['findings'])} checks. Full report: "
        f"`audit_report_{scorecard['audit_stage']}.json`.",
        "",
        "---",
        "*Scorecard format inspired by structured dataset-documentation "
        "practices — Datasheets for Datasets ([arXiv:1803.09010]"
        "(https://arxiv.org/abs/1803.09010)) and scorecards for synthetic "
        "data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*",
    ]
    return "\n".join(lines) + "\n"
