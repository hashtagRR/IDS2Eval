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

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import features, version_info

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
        "ids2eval": version_info.get_version_info(),
        "packages": _package_versions(),
    }
    (run_dir / "environment.json").write_text(json.dumps(info, indent=2))


def write_resolved_config(run_dir: Path, cfg: dict) -> None:
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg, indent=2, default=str))


def _content_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def write_dataset_fingerprint(run_dir: Path, train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> None:
    """Real, content-based proof of what data this run used - distinct from
    cache.py's fingerprint (which exists to answer "can I skip reloading",
    keyed on cheap file stats) and dataset_cfg source-file stats. This one
    hashes the actual loaded DataFrame contents, so it also catches a
    resplit or a cache-invalidation edge case the file-stats check missed,
    not just "did the source CSV change".
    """
    label_col = cfg["schema"]["label_column"]
    fingerprint = {
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "feature_count": len(features.feature_columns(train_df, cfg)),
        "train_class_distribution": {str(k): int(v) for k, v in train_df[label_col].value_counts().items()},
        "test_class_distribution": {str(k): int(v) for k, v in test_df[label_col].value_counts().items()},
        "train_content_hash": _content_hash(train_df),
        "test_content_hash": _content_hash(test_df),
    }
    (run_dir / "dataset_fingerprint.json").write_text(json.dumps(fingerprint, indent=2))


def write_run_status(run_dir: Path, status: str, failed_stage: str | None = None, error: str | None = None) -> None:
    payload = {
        "status": status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "failed_stage": failed_stage,
        "error": error,
    }
    (run_dir / "run_status.json").write_text(json.dumps(payload, indent=2))
