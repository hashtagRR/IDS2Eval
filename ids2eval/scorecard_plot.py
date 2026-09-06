"""Renders the scorecard as a chart-only figure (PDF + PNG).

PDF is the publication-grade vector figure meant to be cited/embedded
directly in a paper; PNG is a raster preview of the exact same figure,
embedded in SCORECARD.md so the chart shows up inline on GitHub (PDFs
don't render in Markdown previews).

Requires matplotlib - an optional extra (`pip install "ids2eval[plots]"`),
not a core dependency, so importing ids2eval.scorecard never needs it.
config.py's validate_config() already confirms matplotlib is importable
before this module is ever touched, so no import-error handling here.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless - never touches a display, safe in CI/servers

import matplotlib.pyplot as plt

_STATUS_COLOR = {"ok": "#1a7f4e", "warning": "#a15c00", "flag": "#b3261e"}
_VERDICT_TEXT = {"passed": "PASSED", "passed_with_warnings": "PASSED WITH WARNINGS", "failed": "FAILED"}
_INK = "#16181c"
_MUTED = "#5b5f6a"
_ACCENT = "#0d8f82"


def _find(findings: list[dict], check: str) -> dict | None:
    return next((f for f in findings if f["check"] == check), None)


def render(scorecard: dict, findings: list[dict], pdf_path: Path, png_path: Path) -> None:
    class_dist = _find(findings, "class_distribution_report")
    leakage = _find(findings, "leakage_screen")
    has_leakage_panel = leakage is not None and "top_features" in leakage.get("details", {})

    n_panels = 1 + (class_dist is not None) + has_leakage_panel
    fig = plt.figure(figsize=(8, 3.0 + n_panels * 2.4))
    height_ratios = [0.8, *([2.2] * n_panels)]
    gs = fig.add_gridspec(nrows=1 + n_panels, ncols=1, height_ratios=height_ratios, hspace=0.6)

    _draw_header(fig.add_subplot(gs[0]), scorecard)
    _draw_status_chart(fig.add_subplot(gs[1]), scorecard)

    row = 2
    if class_dist is not None:
        _draw_class_distribution(fig.add_subplot(gs[row]), class_dist)
        row += 1
    if has_leakage_panel:
        _draw_feature_importance(fig.add_subplot(gs[row]), leakage)
        row += 1

    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _draw_header(ax, scorecard: dict) -> None:
    ax.axis("off")
    verdict = scorecard["overall_status"]
    ax.text(0, 0.75, "IDS2Eval Scorecard", fontsize=16, fontweight="bold", color=_INK, transform=ax.transAxes)
    ax.text(0, 0.3, scorecard["dataset_name"], fontsize=11, color=_MUTED, transform=ax.transAxes)
    ax.text(
        1, 0.5, _VERDICT_TEXT[verdict], fontsize=13, fontweight="bold", color="white",
        ha="right", va="center", transform=ax.transAxes,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": _STATUS_COLOR.get(
            {"passed": "ok", "passed_with_warnings": "warning", "failed": "flag"}[verdict]
        ), "edgecolor": "none"},
    )


def _draw_status_chart(ax, scorecard: dict) -> None:
    counts = {"ok": 0, "warning": 0, "flag": 0}
    for f in scorecard["findings"]:
        counts[f["status"]] += 1
    labels = ["ok", "warning", "flag"]
    values = [counts[label] for label in labels]
    bars = ax.bar(labels, values, color=[_STATUS_COLOR[label] for label in labels], width=0.5)
    ax.bar_label(bars, padding=3, color=_INK, fontsize=10)
    ax.set_title(f"{sum(values)} checks, by status", fontsize=11, color=_INK, loc="left")
    ax.set_ylim(0, max([*values, 1]) * 1.3)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_yticks([])
    ax.tick_params(colors=_MUTED)


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
    ax.set_xticklabels(classes, rotation=20, ha="right", fontsize=9)
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
