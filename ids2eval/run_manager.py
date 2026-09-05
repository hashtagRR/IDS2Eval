"""Per-run experiment directories, retention cleanup, and run metadata.

Deliberately separate from the load-cache (ids2eval/cache.py): that
cache lives at a FIXED output.dir/.cache/ specifically so a second run
with the same config reuses it. Per-run artifacts (results, reports,
metadata) go in output.dir/runs/<timestamp>/ instead, one new directory
per invocation, so results are never silently overwritten - retention
(output.keep_runs) prunes old ones instead of letting them accumulate
forever, but .cache/ is never touched by that cleanup.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

RUNS_DIRNAME = "runs"


def create_run_dir(output_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
    run_dir = output_dir / RUNS_DIRNAME / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def cleanup_old_runs(output_dir: Path, keep_runs: int | None) -> None:
    if keep_runs is None:
        return
    runs_dir = output_dir / RUNS_DIRNAME
    if not runs_dir.exists():
        return
    run_dirs = sorted((p for p in runs_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    for stale in run_dirs[:-keep_runs] if keep_runs > 0 else run_dirs:
        for f in stale.rglob("*"):
            if f.is_file():
                f.unlink()
        for d in sorted(stale.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if d.is_dir():
                d.rmdir()
        stale.rmdir()


def _package_versions() -> dict:
    versions = {}
    for pkg in ("pandas", "numpy", "scikit-learn", "scipy", "imbalanced-learn", "xgboost", "pyyaml", "pyarrow"):
        module_name = {"scikit-learn": "sklearn", "imbalanced-learn": "imblearn", "pyyaml": "yaml"}.get(pkg, pkg)
        try:
            mod = __import__(module_name)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg] = "not installed"
    return versions


def write_environment_info(run_dir: Path) -> None:
    info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "packages": _package_versions(),
    }
    (run_dir / "environment.json").write_text(json.dumps(info, indent=2))


def write_resolved_config(run_dir: Path, cfg: dict) -> None:
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg, indent=2, default=str))
