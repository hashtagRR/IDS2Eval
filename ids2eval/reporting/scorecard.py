"""Formalizes audit findings into a citable pass/fail scorecard.

Not a new check. A rollup of the audit findings, dataset fingerprint, and
tool version already computed elsewhere, into one stable, versioned artifact
a paper can point to (e.g. "this result was obtained on a dataset that
passed the following IDS2Eval checks"). See guide/checks.md's "The
scorecard" section for the prior art this format draws on.

SCHEMA_VERSION is independent of ids2eval's own package version: it only
changes if this dict's shape changes, so a citation naming a schema version
stays parseable even after ids2eval itself moves on. 1.1 is additive over
1.0 (adds "checks", "counts", "dedup_effect", "previous_run_comparison";
every 1.0 key is unchanged).
"checks" has one entry per check: {check, category, before, after} - category is
"audit" or "known_issue" (see ids2eval.audit.KNOWN_ISSUE_CHECKS) - each side
{status, summary} or null - "after" is null throughout when dedup didn't run.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from .. import version_info
from ..audit import KNOWN_ISSUE_CHECKS, STRUCTURAL_CHECKS

SCHEMA_VERSION = "1.1"

_STATUS_RANK = {"ok": 0, "warning": 1, "flag": 2}
_OVERALL_STATUS = {"ok": "passed", "warning": "passed_with_warnings", "flag": "failed"}
_STATUS_EMOJI = {"ok": "✅", "warning": "⚠️", "flag": "🚩"}
_STATUS_BADGE = {"ok": "pass", "warning": "warn", "flag": "flag"}
_VERDICT_LABEL = {
    "passed": "✅ Passed",
    "passed_with_warnings": "⚠️ Passed with warnings",
    "failed": "❌ Failed",
}
_VERDICT_PLAIN = {"passed": "Passed", "passed_with_warnings": "Passed with warnings", "failed": "Failed"}
_VERDICT_STATUS = {"passed": "ok", "passed_with_warnings": "warning", "failed": "flag"}

# Hover text for each check in SCORECARD.html: what it measures, and the exact
# rule that turns a measurement into ok/warning/flag. Keep the rules in sync
# with the thresholds in ids2eval/audit/ - they're restated here, not imported,
# because a sentence has to say "more than 1 point", not "MATERIAL_DROP_THRESHOLD".
CHECK_INFO = {
    "dedup_check": (
        "Exact duplicate feature rows: within train, within test, and test rows whose features exactly "
        "match a train row (labels ignored). Test data sharing under 10% with train is a common industry "
        "rule of thumb (Zhou et al. 2024) - this check is stricter, since any overlap at all measures "
        "memorization rather than generalization.",
        "Flag: any test row matches a train row. Warning: duplicates only within a split.",
    ),
    "label_conflict_check": (
        "Groups rows by identical features (same columns dedup_check compares on) and checks whether "
        "every row in a group has the same label. Must run on raw data: preprocessing.dedup already "
        "collapses these groups to one arbitrarily-kept label, so it always reports zero after cleaning.",
        "Flag: any feature vector maps to more than one label - the ground truth contradicts itself.",
    ),
    "leakage_screen": (
        "Fits a random forest on all features and checks whether one or two features carry most of the "
        "importance - a shortcut a model can learn instead of attack behavior.",
        "Flag: the top feature holds more than 50% of importance, or the top two more than 70%.",
    ),
    "one_rule_check": (
        "Fits a single depth-1 decision tree (one feature, one threshold) and reports the winning rule "
        "in plain language. Per Wu & Keogh 2021: most widely-used time-series anomaly benchmarks turned "
        "out solvable by a single line of code, which meant published algorithm comparisons on them were "
        "measuring nothing.",
        "Flag: the one-rule classifier reaches above 95% test accuracy on its own.",
    ),
    "identity_column_flag": (
        "How well each configured id-like column (IP, port, MAC) predicts the label on its own, as a "
        "standalone ROC AUC.",
        "Flag: AUC above 0.8. Always ok when no schema.id_like_columns are configured.",
    ),
    "port_protocol_shortcut_check": (
        "How well a declared port-like column combined with a proto-like column predicts the label, as a "
        "standalone ROC AUC - the same method as identity_column_flag, applied to the pair rather than "
        "either column alone.",
        "Flag: AUC above 0.8. Always ok when no port-like and proto-like column pair is found.",
    ),
    "temporal_leakage_check": (
        "How well schema.timestamp_column alone predicts the label, as a standalone ROC AUC - datasets "
        "collected as scenario-specific time windows (attack X launched 2-3pm, attack Y 3-4pm, ...) let "
        "a model win by learning 'when', not 'what' (Wu & Keogh 2021's 'run-to-failure bias', confirmed "
        "on this project's own CIC-IDS2018 run: Timestamp alone reached AUC 0.93).",
        "Flag: AUC above 0.8. Always ok when no schema.timestamp_column is configured.",
    ),
    "flow_group_leakage_check": (
        "Hashes schema.flow_id_columns (typically a 5-tuple) for train and test and checks whether any "
        "flow identity appears on both sides of the split - a model can partly recognize the connection "
        "instead of the attack behavior on those rows.",
        "Flag: any flow identity present in both train and test. Always ok when no "
        "schema.flow_id_columns is configured.",
    ),
    "homogeneity_test": (
        "Per class: are test rows closer to their nearest train row than train rows are to each other? "
        "One-sided Mann-Whitney test on nearest-neighbour distances, up to 500 rows per class.",
        "Flag: p < 0.05 in any class. Not corrected for testing many classes, so a single flag is weak evidence.",
    ),
    "resplit_falsification": (
        "Retrains with a grouped split (no session from dataset.group_columns on both sides) and compares "
        "accuracy against a random split. Rebuilds both splits from the raw data itself, so its result is "
        "the same whether or not preprocessing.dedup ran.",
        "Flag: grouped-split accuracy is more than 1 percentage point lower.",
    ),
    "class_distribution_report": (
        "Class counts in train and test, the majority:minority ratio, and rare classes.",
        "Warning: ratio above 100:1, or any class below 1% of train.",
    ),
    "low_cardinality_warning": (
        "Unique values in each id-like column - few values let a model memorize specific hosts.",
        "Warning: fewer than 50 unique values.",
    ),
    "schema_fingerprint_check": (
        "Whether the column names match a flow extractor with documented bugs (currently CICFlowMeter). "
        "Looks only at column names, which dedup never changes, so its result is the same on raw and "
        "cleaned data.",
        "Warning: 60% or more of the extractor's signature columns are present - a caution about the "
        "extractor, not evidence that this copy is affected.",
    ),
    "data_integrity_check": (
        "Missing labels, missing values, +-inf values, and constant features (a single unique value) in train.",
        "Flag: any missing label. Warning: any of the others.",
    ),
    "synthetic_realism_check": (
        "Trains a classifier to tell this dataset apart from audit.reference_dataset, plus per-feature "
        "KS divergence.",
        "Flag: the classifier separates them with AUC above 0.9.",
    ),
    "cross_dataset_drift_check": (
        "Trains on this dataset, tests on audit.reference_dataset, and compares accuracy.",
        "Flag: accuracy drops by more than 10 percentage points.",
    ),
    "known_issue_lookup": (
        "Looks the dataset name up in a hand-curated list of published problems with specific datasets. "
        "Looks only at the name, so its result is the same on raw and cleaned data.",
        "Warning: a match. Ok only means the dataset isn't in the list, not that it has no known issues.",
    ),
    "seed_sensitivity_check": (
        "Re-fits leakage_screen and one_rule_check across 5 seeds and checks whether their flag/ok "
        "conclusion holds up, not just the point estimate a single seed happened to produce "
        "(D'Amour et al. 2022's underspecification finding).",
        "Warning: either check's verdict changed across seeds.",
    ),
}

_TWO_RUNS_NOTE = (
    "Every check ran twice: on the raw data as loaded, and on the cleaned data - the same data with exact "
    "duplicate rows removed, nothing else changed."
)

_KNOWN_ISSUES_NOTE = (
    "Documented facts about this dataset or the tool that produced it, from published research - not "
    "measured from this run's data, and nothing in this run's config can fix what they report."
)

_VERDICT_RULE = "any flag → failed · warnings only → passed with warnings · all ok → passed"
_PRIOR_ART = (
    "Scorecard format inspired by structured dataset-documentation practices. Datasheets for "
    "Datasets (arXiv:1803.09010) and scorecards for synthetic data evaluation (arXiv:2406.11143)."
)


def _check_rows(findings_before: list[dict] | None, findings_after: list[dict] | None) -> list[dict]:
    """One entry per check, with that check's result in each audit pass side
    by side - so every row has the same shape, and a status that changed
    across dedup is visible by comparing two columns rather than two rows.
    """
    before_by = {f["check"]: f for f in findings_before or []}
    after_by = {f["check"]: f for f in findings_after or []}
    return [
        {
            "check": check,
            "category": "known_issue" if check in KNOWN_ISSUE_CHECKS else "audit",
            "before": _result(before_by.get(check)),
            "after": _result(after_by.get(check)),
        }
        for check in dict.fromkeys([*before_by, *after_by])
    ]


def _result(finding: dict | None) -> dict | None:
    return None if finding is None else {"status": finding["status"], "summary": finding["summary"]}


def _dedup_effect(findings_before: list[dict] | None) -> dict | None:
    dedup = next((f for f in findings_before or [] if f["check"] == "dedup_check"), None)
    if dedup is None or "train_rows_raw" not in dedup.get("details", {}):
        return None
    d = dedup["details"]
    return {k: int(d[k]) for k in (
        "train_rows_raw", "train_rows_deduped", "train_duplicates_dropped",
        "test_rows_raw", "test_rows_deduped", "test_leakage_dropped", "test_duplicates_dropped",
    ) if k in d}


def build_scorecard(
    findings: list[dict],
    audit_stage: str,
    cfg: dict,
    fingerprint: dict,
    findings_before: list[dict] | None = None,
) -> dict:
    """audit_stage is "before" or "after" - which of
    audit_report_before.json/audit_report_after.json these findings came
    from (whichever is the FINAL state of the data shipped in this run:
    "after" if preprocessing.dedup ran, else "before"). The verdict is
    always judged on these final findings.

    findings_before is the pre-dedup pass, passed only when audit_stage is
    "after": it adds the before/after comparison rows and the dedup effect,
    never the verdict - a flag dedup has already fixed isn't a flag on the
    data this run shipped.
    """
    worst = max((f["status"] for f in findings), key=lambda s: _STATUS_RANK[s], default="ok")
    version = version_info.get_version_info()
    counts = {"ok": 0, "warning": 0, "flag": 0}
    for f in findings:
        counts[f["status"]] += 1

    if audit_stage == "after":
        rows = _check_rows(findings_before, findings)
    else:
        rows = _check_rows(findings, None)

    return {
        "scorecard_schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_name": cfg["dataset"]["name"],
        "ids2eval_version": version["version"],
        "ids2eval_git_commit": version["git_commit"],
        "audit_stage": audit_stage,
        "overall_status": _OVERALL_STATUS[worst],
        "counts": counts,
        "findings": [{"check": f["check"], "status": f["status"], "summary": f["summary"]} for f in findings],
        "checks": rows,
        # Only once dedup actually ran - before it, these are hypothetical counts.
        "dedup_effect": _dedup_effect(findings_before) if audit_stage == "after" else None,
        "dataset_fingerprint": {
            "train_rows": fingerprint["train_rows"],
            "test_rows": fingerprint["test_rows"],
            "feature_count": fingerprint.get("feature_count"),
            "train_content_hash": fingerprint["train_content_hash"],
            "test_content_hash": fingerprint["test_content_hash"],
        },
    }


def _counts(scorecard: dict) -> dict:
    # Scorecards written under schema 1.0 have no "counts" key.
    if "counts" in scorecard:
        return scorecard["counts"]
    counts = {"ok": 0, "warning": 0, "flag": 0}
    for f in scorecard["findings"]:
        counts[f["status"]] += 1
    return counts


def _rows(scorecard: dict) -> list[dict]:
    """Per-check rows plus what the renderers need: the final result, the
    pre-dedup summary when it differs, and whether the status moved.
    Scorecards written under schema 1.0 have no "checks" - rebuilt from
    "findings", which is the final pass.
    """
    if scorecard.get("checks"):
        rows = scorecard["checks"]
    else:
        final = [{"check": f["check"], "status": f["status"], "summary": f["summary"]} for f in scorecard["findings"]]
        rows = _check_rows(final, None) if scorecard["audit_stage"] == "before" else _check_rows(None, final)
    out = []
    for r in rows:
        b, a = r["before"], r["after"]
        final = a or b
        out.append({
            **r,
            "summary": final["summary"],
            "summary_before": b["summary"] if a and b and b["summary"] != a["summary"] else None,
            "moved": bool(a and b and a["status"] != b["status"]),
            # Provably the same check run once, not two independent measurements of the
            # same result - see STRUCTURAL_CHECKS. Renderers show one status, not two.
            "structural": r["check"] in STRUCTURAL_CHECKS,
        })
    return out


def _has_after(scorecard: dict) -> bool:
    return scorecard["audit_stage"] == "after"


def _split_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(audit rows, known-issue rows) - see KNOWN_ISSUE_CHECKS. Known-issue rows always
    render with a single Status column: their result can't differ between raw and
    cleaned data (see CHECK_INFO), so showing two columns would only invite the
    question this split exists to answer - see _rows()'s "category" field.
    """
    audit_rows = [r for r in rows if r["category"] == "audit"]
    known_rows = [r for r in rows if r["category"] == "known_issue"]
    return audit_rows, known_rows


def _md_status(result: dict | None) -> str:
    return "n/a" if result is None else f"{_STATUS_EMOJI[result['status']]} {_STATUS_BADGE[result['status']]}"


def _drift_lines(scorecard: dict) -> list[str]:
    """Markdown bullet lines for the previous-run comparison, or [] if the
    scorecard carries none (schema 1.0, or no previous run existed).
    """
    drift = scorecard.get("previous_run_comparison")
    if not drift:
        return []
    lines = [f"Compared to `{drift['previous_run']}` ({drift['previous_generated_at']})."]
    if drift["fingerprint_changed"]:
        lines.append(
            "The underlying data changed since then (a different content hash) - the "
            "comparison below may reflect a different dataset, not drift within the same one."
        )
    if drift["changed_checks"]:
        for c in drift["changed_checks"]:
            lines.append(f"- `{c['check']}`: {c['previous_status']} to {c['current_status']}")
    else:
        lines.append("No check's status changed since the previous run.")
    return lines


def citation_text(scorecard: dict) -> str:
    counts = _counts(scorecard)
    return (
        f"This result was obtained on a dataset audited with IDS2Eval "
        f"v{scorecard['ids2eval_version']} (scorecard schema "
        f"{scorecard['scorecard_schema_version']}), which reported "
        f"{scorecard['overall_status'].replace('_', ' ')}, "
        f"{counts['ok']} ok, {counts['warning']} warning(s), {counts['flag']} flag(s) "
        f"across {len(scorecard['findings'])} checks. Full report: "
        f"audit_report_{scorecard['audit_stage']}.json."
    )


def render_markdown(scorecard: dict, has_plot: bool = False) -> str:
    counts = _counts(scorecard)
    rows = _rows(scorecard)
    fp = scorecard["dataset_fingerprint"]

    lines = [
        "# IDS2Eval Scorecard",
        "",
        f"**Dataset:** {scorecard['dataset_name']}",
        f"**Overall status:** {_VERDICT_LABEL[scorecard['overall_status']]}"
        f", {counts['ok']} ok, {counts['warning']} warning(s), {counts['flag']} flag(s)",
        f"**Generated:** {scorecard['generated_at']}",
        f"**IDS2Eval version:** {scorecard['ids2eval_version']}"
        + (f" (git {scorecard['ids2eval_git_commit'][:7]})" if scorecard["ids2eval_git_commit"] else ""),
        f"**Scorecard schema version:** {scorecard['scorecard_schema_version']}",
        f"**Verdict judged on:** {'cleaned data (exact duplicates removed)' if _has_after(scorecard) else 'raw data'}",
        "",
        "A full, styled version of this scorecard is in `SCORECARD.html`.",
    ]
    if has_plot:
        # An explicit width, not bare markdown ![]() syntax - GitHub renders
        # an embedded image at full native size otherwise, which dwarfs the
        # rest of the page for a figure this tall.
        lines += ["", '<img src="scorecard.png" alt="IDS2Eval Scorecard" width="760">']
    audit_rows, known_rows = _split_rows(rows)
    has_after = _has_after(scorecard)

    lines += [
        "",
        "## Checks",
        "",
        "Findings from this run's own data. Each one can, in principle, be reacted to - "
        "by dropping a column, resampling, switching split modes, or just noting the caveat.",
        "",
        "| # | Check | Raw data | Cleaned data | Summary |" if has_after else "| # | Check | Status | Summary |",
        "|---|---|---|---|---|" if has_after else "|---|---|---|---|",
    ]
    for i, r in enumerate(audit_rows, 1):
        if has_after and r["structural"]:
            statuses = f"{_md_status(r['before'])} (same on raw and cleaned data) |"
        elif has_after:
            statuses = f"{_md_status(r['before'])} | {_md_status(r['after'])} |"
        else:
            statuses = f"{_md_status(r['before'])} |"
        lines.append(
            f"| {i} | `{r['check']}` | {statuses} {r['summary']}"
            + (f"<br>*raw data:* {r['summary_before']}" if r["summary_before"] else "") + " |"
        )

    if known_rows:
        lines += [
            "",
            "## Known issues",
            "",
            _KNOWN_ISSUES_NOTE,
            "",
            "| # | Check | Status | Summary |",
            "|---|---|---|---|",
        ]
        for i, r in enumerate(known_rows, 1):
            lines.append(f"| {i} | `{r['check']}` | {_md_status(r['before'])} | {r['summary']} |")

    effect = scorecard.get("dedup_effect")
    if effect:
        lines += [
            "",
            "## What cleaning removed",
            "",
            f"- Train: {effect['train_rows_raw']:,} → {effect['train_rows_deduped']:,} rows "
            f"({effect['train_duplicates_dropped']:,} duplicates dropped)",
            f"- Test: {effect['test_rows_raw']:,} → {effect['test_rows_deduped']:,} rows "
            f"({effect['test_leakage_dropped']:,} train-leaking rows and "
            f"{effect['test_duplicates_dropped']:,} test-internal duplicates dropped)",
        ]

    drift_lines = _drift_lines(scorecard)
    if drift_lines:
        lines += ["", "## Compared to the previous run", "", *drift_lines]

    lines += [
        "",
        "## Dataset fingerprint",
        "",
        f"- Train rows: {fp['train_rows']:,} · test rows: {fp['test_rows']:,}"
        + (f" · features: {fp['feature_count']}" if fp.get("feature_count") is not None else ""),
        f"- Train content hash: `{fp['train_content_hash']}`",
        f"- Test content hash: `{fp['test_content_hash']}`",
        "",
        "## Citing this result",
        "",
        "> " + citation_text(scorecard)
        + (" A vector figure of this chart is at `scorecard.pdf`, ready to cite directly." if has_plot else ""),
        "",
        f"Verdict rule: {_VERDICT_RULE}.",
        "",
        "---",
        "*Scorecard format inspired by structured dataset-documentation "
        "practices. Datasheets for Datasets ([arXiv:1803.09010]"
        "(https://arxiv.org/abs/1803.09010)) and scorecards for synthetic "
        "data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*",
    ]
    return "\n".join(lines) + "\n"


_HTML_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181c;--muted:#6b6f7a;--line:#e6e8ec;--bar:#16181c;--bar-ink:#f2f3f5;
--ok:#1a7f4e;--ok-bg:#e3f4ea;--warn:#a15c00;--warn-bg:#fdf0da;--flag:#b3261e;--flag-bg:#fbe3e1;--code:#f0f1f4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#101216;--card:#171a1f;--ink:#e8eaee;
--muted:#9aa0ab;--line:#2a2e36;--bar:#0b0c0f;--bar-ink:#e8eaee;--ok:#5cc98f;--ok-bg:#15301f;--warn:#f0b35a;
--warn-bg:#35270f;--flag:#f08a80;--flag-bg:#3a1916;--code:#20242b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",
Helvetica,Arial,sans-serif}
.mono,code,td.check{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.page{max-width:1080px;margin:24px auto;padding:0 16px}
.sheet{background:var(--card);border:1px solid var(--line);border-left:8px solid var(--accent);border-radius:10px;
padding:36px 40px}
.eyebrow{color:var(--muted);font-size:1.05rem;margin:0}
h1{font-size:1.9rem;line-height:1.2;margin:.2rem 0 .5rem}
.lede{color:var(--muted);margin:0 0 28px}
.card{border:1px solid var(--line);border-radius:8px}
.bar{background:var(--bar);color:var(--bar-ink);display:flex;justify-content:space-between;gap:12px;
flex-wrap:wrap;padding:12px 24px;border-radius:7px 7px 0 0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.bar b{font-weight:700}
.body{padding:20px 24px 8px}
.meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;padding-bottom:18px;
border-bottom:1px solid var(--line)}
.meta .k{color:var(--muted);font-size:.82rem}
.meta .v{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;margin-top:10px}
th{text-align:left;color:var(--muted);font-size:.82rem;font-weight:600;padding:10px;border-bottom:1px solid var(--line)}
td{padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}
td{overflow-wrap:break-word}
td.num{color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.82rem;
width:1%;white-space:nowrap}
td.check{white-space:nowrap;position:relative}
.info{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;margin-left:6px;
border:1px solid var(--muted);border-radius:50%;color:var(--muted);font:700 10px/1 -apple-system,BlinkMacSystemFont,
"Segoe UI",Helvetica,Arial,sans-serif;cursor:help;vertical-align:1px}
.info:hover,.info:focus-visible{color:var(--ink);border-color:var(--ink);outline:none}
.tip{display:none;position:absolute;left:4px;top:calc(100% - 4px);z-index:10;width:min(360px,calc(100vw - 48px));
padding:10px 12px;background:var(--bar);color:var(--bar-ink);border-radius:8px;box-shadow:0 8px 24px rgb(0 0 0/.28);
font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;white-space:normal;
text-align:left;overflow-wrap:normal}
.tip .tk{display:block;font-size:.7rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;opacity:.65}
.tip .tv{display:block;margin-bottom:8px}.tip .tv:last-child{margin-bottom:0}
.info:hover+.tip,.info:focus+.tip{display:block}
td.status{white-space:nowrap}
.same-note{color:var(--muted);font-size:.78rem;margin-left:6px}
.badge{display:inline-block;font:700 .75rem/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
padding:5px 9px;border-radius:999px}
.b-ok{color:var(--ok);background:var(--ok-bg)}.b-warning{color:var(--warn);background:var(--warn-bg)}
.b-flag{color:var(--flag);background:var(--flag-bg)}.b-none{color:var(--muted);background:transparent}
tr.moved td{background:color-mix(in srgb,var(--accent) 4%,transparent)}
.was{color:var(--muted);font-size:.82rem;margin-top:3px}
h2{font-size:1.05rem;margin:28px 0 10px}
h2.first{margin-top:0}
.section-note{margin:0 0 4px;color:var(--muted);font-size:.9rem}
.effect{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.tile{border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.tile .k{color:var(--muted);font-size:.82rem}.tile .v{font-size:1.05rem;font-weight:600}
blockquote{margin:0;padding:14px 16px;border-left:3px solid var(--accent);background:var(--code);border-radius:4px}
.hash{font-size:.8rem;overflow-wrap:anywhere}
.foot{color:var(--muted);font-size:.8rem;margin-top:28px;border-top:1px solid var(--line);padding-top:12px}
@media (max-width:720px){.sheet{padding:24px 18px}.meta{grid-template-columns:repeat(2,minmax(0,1fr))}
.effect{grid-template-columns:1fr}
thead{display:none}table,tbody,tr,td{display:block;width:100%}
tr{border-bottom:1px solid var(--line);padding:10px 4px}td{border:0;padding:3px 0}
td.num,td.check,td.status{display:inline-block;width:auto;margin-right:10px;vertical-align:middle}
td.status[data-label]:not([data-label=""])::before{content:attr(data-label) " ";color:var(--muted);font-size:.75rem;
font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.same-note{display:block;margin:2px 0 0}
td.check{white-space:normal}.tip{left:0;width:calc(100vw - 72px)}
tr.moved{background:color-mix(in srgb,var(--accent) 4%,transparent)}tr.moved td{background:none}}
@media print{body{background:#fff}.page{margin:0;max-width:none}.sheet{border-radius:0}.info,.tip{display:none}}
"""

_ACCENT = {"ok": "#1a8a5a", "warning": "#c07a10", "flag": "#c0392b"}


def _info_html(check: str, row: int) -> str:
    """The hover/focus explainer for one check - CSS only, no script, so the
    page stays self-contained and still works under the dashboard's CSP.
    """
    if check not in CHECK_INFO:
        return ""
    what, rule = CHECK_INFO[check]
    tip_id = f"tip-{row}"
    return (
        f'<span class="info" tabindex="0" role="button" aria-label="About {html.escape(check)}" '
        f'aria-describedby="{tip_id}">i</span>'
        f'<span class="tip" role="tooltip" id="{tip_id}"><span class="tk">What it checks</span>'
        f'<span class="tv">{html.escape(what)}</span><span class="tk">Rule</span>'
        f'<span class="tv">{html.escape(rule)}</span></span>'
    )


def render_html(scorecard: dict) -> str:
    """A standalone, self-contained page (no external assets) - opens from
    disk, prints to PDF from any browser, and is what the web UI shows.
    """
    e = html.escape
    counts = _counts(scorecard)
    rows = _rows(scorecard)
    fp = scorecard["dataset_fingerprint"]
    verdict = scorecard["overall_status"]
    commit = scorecard["ids2eval_git_commit"]
    generated = scorecard["generated_at"][:16].replace("T", " ") + " UTC"
    n_checks = len(scorecard["findings"])
    has_after = _has_after(scorecard)
    moved = any(r["moved"] for r in rows)

    def badge(result: dict | None) -> str:
        return '<span class="badge b-none">n/a</span>' if result is None else \
            f'<span class="badge b-{result["status"]}">{_STATUS_BADGE[result["status"]]}</span>'

    def status_cells(r: dict) -> str:
        if not has_after:
            return f'<td class="status">{badge(r["before"])}</td>'
        if r["structural"]:
            # One measurement, not two: a single cell spanning both data columns, with a
            # muted note in place of a second badge - showing the same colored badge twice
            # would look like an independent second result that just happened to agree.
            return (
                f'<td class="status" colspan="2">{badge(r["before"])} '
                f'<span class="same-note">same on raw and cleaned data</span></td>'
            )
        return (
            f'<td class="status" data-label="raw">{badge(r["before"])}</td>'
            f'<td class="status" data-label="cleaned">{badge(r["after"])}</td>'
        )

    def audit_row(i: int, r: dict) -> str:
        return (
            f'<tr class="{"moved" if r["moved"] else ""}">'
            f'<td class="num">{i}</td>'
            f'<td class="check">{e(r["check"])}{_info_html(r["check"], i)}</td>'
            + status_cells(r)
            + f"<td>{e(r['summary'])}"
            + (f'<div class="was">raw data: {e(r["summary_before"])}</div>' if r["summary_before"] else "")
            + "</td></tr>"
        )

    def known_issue_row(i: int, r: dict) -> str:
        # Always one status - see _split_rows(): can't differ between raw and cleaned data.
        return (
            f'<tr><td class="num">{i}</td>'
            f'<td class="check">{e(r["check"])}{_info_html(r["check"], i + 1000)}</td>'
            f'<td class="status">{badge(r["before"])}</td>'
            f"<td>{e(r['summary'])}</td></tr>"
        )

    audit_rows, known_rows = _split_rows(rows)
    audit_body = "\n".join(audit_row(i, r) for i, r in enumerate(audit_rows, 1))
    header = "<th>#</th><th>Check</th><th>Raw data</th><th>Cleaned data</th><th>Summary</th>" if has_after \
        else "<th>#</th><th>Check</th><th>Status</th><th>Summary</th>"

    known_issues_html = ""
    if known_rows:
        known_body = "\n".join(known_issue_row(i, r) for i, r in enumerate(known_rows, 1))
        known_issues_html = f"""<h2>Known issues</h2>
<p class="section-note">{e(_KNOWN_ISSUES_NOTE)}</p>
<table>
<thead><tr><th>#</th><th>Check</th><th>Status</th><th>Summary</th></tr></thead>
<tbody>
{known_body}
</tbody></table>"""

    tally = f"{counts['ok']} ok, {counts['warning']} warning(s), {counts['flag']} flag(s) across {n_checks} checks"
    if has_after:
        lede = f"{_TWO_RUNS_NOTE} Verdict ({tally}) is judged on the cleaned data."
        if moved:
            lede += " Highlighted rows are checks whose status differs between the two."
    else:
        lede = f"{tally}, run once on the raw data (duplicate removal was off for this run)."

    drift = scorecard.get("previous_run_comparison")
    drift_html = ""
    if drift:
        if drift["changed_checks"]:
            rows = "".join(
                f"<li><code>{e(c['check'])}</code>: {e(c['previous_status'])} to {e(c['current_status'])}</li>"
                for c in drift["changed_checks"]
            )
            changes = f"<ul>{rows}</ul>"
        else:
            changes = "<p>No check's status changed since the previous run.</p>"
        fp_note = (
            '<p class="section-note">The underlying data changed since then (a different content hash) - '
            "the comparison below may reflect a different dataset, not drift within the same one.</p>"
            if drift["fingerprint_changed"] else ""
        )
        drift_html = f"""<h2>Compared to the previous run</h2>
<p class="section-note">Compared to <code>{e(drift['previous_run'])}</code>
({e(str(drift['previous_generated_at']))}).</p>
{fp_note}
{changes}"""

    effect = scorecard.get("dedup_effect")
    effect_html = ""
    if effect:
        effect_html = (
            '<h2>What cleaning removed</h2><div class="effect">'
            f'<div class="tile"><div class="k">Train rows</div><div class="v mono">{effect["train_rows_raw"]:,} → '
            f'{effect["train_rows_deduped"]:,}</div><div class="k">{effect["train_duplicates_dropped"]:,} '
            "duplicates dropped</div></div>"
            f'<div class="tile"><div class="k">Test rows</div><div class="v mono">{effect["test_rows_raw"]:,} → '
            f'{effect["test_rows_deduped"]:,}</div><div class="k">{effect["test_leakage_dropped"]:,} train-leaking '
            f'+ {effect["test_duplicates_dropped"]:,} internal duplicates dropped</div></div></div>'
        )

    features = f" · {fp['feature_count']} features" if fp.get("feature_count") is not None else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IDS2Eval Scorecard · {e(scorecard['dataset_name'])}</title>
<style>{_HTML_CSS}</style></head>
<body style="--accent:{_ACCENT[_VERDICT_STATUS[verdict]]}"><div class="page"><div class="sheet">
<p class="eyebrow">IDS2Eval: the scorecard, not a magic number</p>
<h1>{e(scorecard['dataset_name'])}: {_VERDICT_PLAIN[verdict]}</h1>
<p class="lede">{e(lede)}</p>
<div class="card">
<div class="bar"><b>SCORECARD</b><span>ids2eval v{e(scorecard['ids2eval_version'])} · generated {e(generated)}</span></div>
<div class="body">
<div class="meta">
<div><div class="k">Dataset fingerprint</div><div class="v">{e(scorecard['dataset_name'])} ·
{e(fp['train_content_hash'][:8])}</div></div>
<div><div class="k">Checks run</div><div class="v">{len(audit_rows)} checks + {len(known_rows)} known issue(s)
· {"raw + cleaned" if has_after else "raw only"}</div></div>
<div><div class="k">Tool / schema version</div><div class="v">v{e(scorecard['ids2eval_version'])}
{f"({e(commit[:7])})" if commit else ""} · schema {e(scorecard['scorecard_schema_version'])}</div></div>
<div><div class="k">Verdict</div><div class="v"><span class="badge b-{_VERDICT_STATUS[verdict]}">
{_VERDICT_PLAIN[verdict].lower()}</span></div></div>
</div>
<h2 class="first">Checks</h2>
<p class="section-note">Findings from this run's own data. Each one can, in principle, be reacted to - by
dropping a column, resampling, switching split modes, or just noting the caveat.</p>
<table>
<thead><tr>{header}</tr></thead>
<tbody>
{audit_body}
</tbody></table>
</div></div>
{known_issues_html}
{drift_html}
{effect_html}
<h2>Dataset fingerprint</h2>
<p class="mono hash">train: {fp['train_rows']:,} rows · test: {fp['test_rows']:,} rows{features}<br>
train sha256 {e(fp['train_content_hash'])}<br>test sha256 {e(fp['test_content_hash'])}</p>
<h2>Citing this result</h2>
<blockquote>{e(citation_text(scorecard))}</blockquote>
<p class="foot">Verdict rule: {e(_VERDICT_RULE)}.<br>{e(_PRIOR_ART)}</p>
</div></div></body></html>
"""
