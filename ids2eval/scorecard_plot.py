"""Renders the scorecard as a figure (PDF + PNG): the verdict, the full
per-check breakdown (name, status, and *why* - the check's own summary
for this run), and diagnostic charts where applicable. A bare status-count
chart was tried first and dropped - "8 ok, 1 warning" means nothing
without seeing which checks and why, so the checks list is the main
content, not an afterthought.

PDF is the publication-grade vector figure meant to be cited/embedded
directly in a paper; PNG is a raster preview of the exact same figure,
embedded in SCORECARD.md so the chart shows up inline on GitHub (PDFs
don't render in Markdown previews) - SCORECARD.md constrains its display
width explicitly, since GitHub renders an embedded image at full native
size otherwise.

Requires matplotlib - an optional extra (`pip install "ids2eval[plots]"`),
not a core dependency, so importing ids2eval.scorecard never needs it.
config.py's validate_config() already confirms matplotlib is importable
before this module is ever touched, so no import-error handling here.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless - never touches a display, safe in CI/servers

import matplotlib.pyplot as plt

_STATUS_COLOR = {"ok": "#1a7f4e", "warning": "#a15c00", "flag": "#b3261e"}
_VERDICT_TEXT = {"passed": "PASSED", "passed_with_warnings": "PASSED WITH WARNINGS", "failed": "FAILED"}
_VERDICT_STATUS = {"passed": "ok", "passed_with_warnings": "warning", "failed": "flag"}
_INK = "#16181c"
_MUTED = "#5b5f6a"
_ACCENT = "#0d8f82"

_SUMMARY_WRAP_WIDTH = 92


def _find(findings: list[dict], check: str) -> dict | None:
    return next((f for f in findings if f["check"] == check), None)


def render(scorecard: dict, findings: list[dict], pdf_path: Path, png_path: Path) -> None:
    class_dist = _find(findings, "class_distribution_report")
    leakage = _find(findings, "leakage_screen")
    has_leakage_panel = leakage is not None and "top_features" in leakage.get("details", {})

    wrapped = [(f, textwrap.wrap(f["summary"], width=_SUMMARY_WRAP_WIDTH) or [""]) for f in findings]
    checks_lines = sum(1 + len(lines) + 0.35 for _, lines in wrapped)
    # Generous on purpose: this panel is raw ax.text(), not axes titles/ticks,
    # so matplotlib's own layout engines can't see its content to avoid
    # collisions with the panel below - the padding has to be manual.
    checks_panel_height = 0.6 + checks_lines * 0.26

    n_diagnostic_panels = (class_dist is not None) + has_leakage_panel
    fig_height = 1.0 + checks_panel_height + n_diagnostic_panels * 2.6
    fig = plt.figure(figsize=(7.5, fig_height))
    height_ratios = [1.0, checks_panel_height, *([2.6] * n_diagnostic_panels)]
    gs = fig.add_gridspec(nrows=2 + n_diagnostic_panels, ncols=1, height_ratios=height_ratios, hspace=0.55)

    _draw_header(fig.add_subplot(gs[0]), scorecard)
    _draw_checks_list(fig.add_subplot(gs[1]), wrapped)

    row = 2
    if class_dist is not None:
        _draw_class_distribution(fig.add_subplot(gs[row]), class_dist)
        row += 1
    if has_leakage_panel:
        _draw_feature_importance(fig.add_subplot(gs[row]), leakage)
        row += 1

    fig.text(
        0.01, 0.005,
        "Verdict rule: any flag -> failed  ·  warnings only -> passed with warnings  ·  all ok -> passed",
        fontsize=7, color=_MUTED,
    )

    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def _draw_header(ax, scorecard: dict) -> None:
    ax.axis("off")
    verdict = scorecard["overall_status"]
    counts = {"ok": 0, "warning": 0, "flag": 0}
    for f in scorecard["findings"]:
        counts[f["status"]] += 1
    counts_text = (
        f"{counts['ok']} ok  ·  {counts['warning']} warning  ·  "
        f"{counts['flag']} flag  ·  {sum(counts.values())} checks"
    )

    ax.text(0, 0.8, "IDS2Eval Scorecard", fontsize=16, fontweight="bold", color=_INK, transform=ax.transAxes)
    ax.text(0, 0.42, scorecard["dataset_name"], fontsize=11, color=_MUTED, transform=ax.transAxes)
    ax.text(0, 0.08, counts_text, fontsize=9.5, color=_INK, transform=ax.transAxes)
    ax.text(
        1, 0.55, _VERDICT_TEXT[verdict], fontsize=13, fontweight="bold", color="white",
        ha="right", va="center", transform=ax.transAxes,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": _STATUS_COLOR[_VERDICT_STATUS[verdict]], "edgecolor": "none"},
    )


def _draw_checks_list(ax, wrapped: list[tuple[dict, list[str]]]) -> None:
    total_lines = sum(1 + len(lines) + 0.35 for _, lines in wrapped)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, max(total_lines, 1))
    ax.axis("off")

    y = total_lines
    for f, lines in wrapped:
        y -= 1
        color = _STATUS_COLOR[f["status"]]
        ax.text(0.0, y, "●", color=color, fontsize=11, va="top")
        ax.text(0.028, y, f["check"], color=_INK, fontsize=9.3, fontweight="bold", family="monospace", va="top")
        ax.text(0.99, y, f["status"], color=color, fontsize=8.8, fontweight="bold", va="top", ha="right")
        for line in lines:
            y -= 1
            ax.text(0.028, y, line, color=_MUTED, fontsize=8.3, va="top")
        y -= 0.35


def _draw_class_distribution(ax, finding: dict) -> None:
    details = finding["details"]
    train_counts, test_counts = details["train"]["counts"], details["test"]["counts"]
    classes = list(train_counts)
    classes += [c for c in test_counts if c not in classes]

    x = range(len(classes))
    width = 0.35
    ax.bar([i - width / 2 for i in x], [train_counts.get(c, 0) for c in classes], width, label="train", color=_ACCENT)
    ax.bar([i + width / 2 for i in x], [test_counts.get(c, 0) for c in classes], width, label="test", color=_MUTED)
    ax.set_yscale("log")
    ax.set_xticks(list(x))
    # Short labels (e.g. numeric 0/1 label columns) sit horizontally - no
    # need to eat vertical space rotating something that already fits.
    needs_rotation = max(len(str(c)) for c in classes) > 6
    if needs_rotation:
        ax.set_xticklabels(classes, rotation=20, ha="right", fontsize=9)
    else:
        ax.set_xticklabels(classes, fontsize=9)
    ax.set_title("Class distribution (log scale)", fontsize=11, color=_INK, loc="left")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=_MUTED)


def _draw_feature_importance(ax, finding: dict) -> None:
    top_features = finding["details"]["top_features"]
    names = list(top_features)[::-1]
    values = [top_features[name] for name in names]
    ax.barh(names, values, color=_STATUS_COLOR["flag"])
    ax.set_title("Top feature importances (leakage_screen)", fontsize=11, color=_INK, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=_MUTED)
