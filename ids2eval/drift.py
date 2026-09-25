"""Compares this run's scorecard against the previous run in the same
output.dir, so a dataset-quality change between two runs of the same
config over time is visible without a person diffing two JSON files by
hand.

Every check here treats each run as fully independent: there is no
mechanism to notice that a source file was quietly swapped, or that a
dataset's duplication rate crept up between one export and the next.
Deequ and whylogs (see general ML data-quality tooling) both track
quality metrics across runs against a metrics repository rather than
only within one; this is a minimal version of that idea, comparing
against the immediately preceding run rather than a full history.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import run_manager

logger = logging.getLogger(__name__)


def find_previous_run(output_dir: Path, current_run_dir: Path) -> Path | None:
    """The most recent other run directory in output_dir that has a
    scorecard.json, or None if there isn't one (a fresh output_dir, or
    every prior run failed before the scorecard stage).
    """
    runs_dir = output_dir / run_manager.RUNS_DIRNAME
    if not runs_dir.is_dir():
        return None
    candidates = sorted(
        p for p in runs_dir.iterdir()
        if p.is_dir() and p != current_run_dir and (p / "scorecard.json").is_file()
    )
    return candidates[-1] if candidates else None


def _status_by_check(scorecard: dict) -> dict[str, str]:
    if scorecard.get("checks"):
        return {r["check"]: (r["after"] or r["before"])["status"] for r in scorecard["checks"]}
    return {f["check"]: f["status"] for f in scorecard.get("findings", [])}


def compare(scorecard: dict, previous_run_dir: Path) -> dict | None:
    """None if the previous run's scorecard.json can't be read - a missing
    comparison is reported as "no previous run" rather than crashing the
    current run over an unrelated one's leftover state.
    """
    try:
        previous = json.loads((previous_run_dir / "scorecard.json").read_text())
    except (OSError, ValueError) as e:
        logger.warning("Could not read previous run's scorecard at %s: %s", previous_run_dir, e)
        return None

    previous_status = _status_by_check(previous)
    current_status = _status_by_check(scorecard)
    changed_checks = [
        {"check": check, "previous_status": previous_status[check], "current_status": status}
        for check, status in current_status.items()
        if check in previous_status and previous_status[check] != status
    ]

    previous_fp = previous.get("dataset_fingerprint", {})
    current_fp = scorecard["dataset_fingerprint"]
    fingerprint_changed = (
        previous_fp.get("train_content_hash") != current_fp.get("train_content_hash")
        or previous_fp.get("test_content_hash") != current_fp.get("test_content_hash")
    )

    return {
        "previous_run": previous_run_dir.name,
        "previous_generated_at": previous.get("generated_at"),
        "previous_verdict": previous.get("overall_status"),
        "fingerprint_changed": fingerprint_changed,
        "changed_checks": changed_checks,
    }
