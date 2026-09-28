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
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .. import version_info
from ..data import features

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


def content_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def content_hash_unordered(df: pd.DataFrame) -> str:
    """Order-independent variant of content_hash: sums per-row hashes rather than
    hashing the row sequence, so identical row content in a different order (or
    split differently across train/test) hashes the same. Used by compare_datasets'
    combined-hash check, which needs exactly that property to detect the same
    underlying data loaded with a different split_ratio/split_mode/seed; content_hash's
    order-sensitive behavior stays the default everywhere else (dataset_fingerprint.json,
    citation keys), which track one specific run's specific split, not row-set equality.
    Sum (not XOR) preserves row-count multiplicity, so duplicate rows still change the
    result - real IDS datasets often contain genuine duplicates, and this check
    shouldn't treat "n copies of a row" the same as "one copy."
    """
    row_hashes = pd.util.hash_pandas_object(df, index=False).to_numpy(dtype="uint64")
    combined = int(row_hashes.sum(dtype="uint64"))
    return hashlib.sha256(combined.to_bytes(8, "little", signed=False)).hexdigest()


def _file_sha256(path: str, chunk_size: int = 1 << 20) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _source_file_manifest(dataset_cfg: dict) -> list[dict]:
    """Per-source-file provenance: the exact bytes this run's data came
    from, independent of how ids2eval parsed them. The same fact this
    project's own example READMEs have recorded by hand ("every file's
    SHA-256 matched the mirror's published checksum"), computed and
    written automatically instead. Hashes the file as stored on disk
    (typically gzipped), matching what a published checksum is normally
    computed against, not the decompressed content.
    """
    paths = dataset_cfg["raw_files"] or [p for p in (dataset_cfg["train_file"], dataset_cfg["test_file"]) if p]
    manifest = []
    for path in paths:
        try:
            size_bytes = os.path.getsize(path)
        except OSError:
            size_bytes = None
        manifest.append({"path": path, "size_bytes": size_bytes, "sha256": _file_sha256(path)})
    return manifest


def compute_dataset_fingerprint(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    """The dict write_dataset_fingerprint writes to disk, exposed on its own
    so a caller that doesn't have (or want) a run directory, like
    ids2eval.reporting.compare_datasets, can compute the same fingerprint
    without a file-writing side effect.
    """
    label_col = cfg["schema"]["label_column"]
    return {
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "feature_count": len(features.feature_columns(train_df, cfg)),
        "train_class_distribution": {str(k): int(v) for k, v in train_df[label_col].value_counts().items()},
        "test_class_distribution": {str(k): int(v) for k, v in test_df[label_col].value_counts().items()},
        "train_content_hash": content_hash(train_df),
        "test_content_hash": content_hash(test_df),
        "columns": list(train_df.columns),
        "source_files": _source_file_manifest(cfg["dataset"]),
    }


def write_dataset_fingerprint(run_dir: Path, train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    """Real, content-based proof of what data this run used - distinct from
    cache.py's fingerprint (which exists to answer "can I skip reloading",
    keyed on cheap file stats) and dataset_cfg source-file stats. This one
    hashes the actual loaded DataFrame contents, so it also catches a
    resplit or a cache-invalidation edge case the file-stats check missed,
    not just "did the source CSV change". Also records the source files'
    own checksums (source_files) and the loaded column schema (columns),
    a provenance manifest a second run, or a second person, can compare
    a claimed-identical dataset against.

    Returns the fingerprint dict too, so callers (e.g. scorecard.py) can
    reuse it without recomputing the content hashes.
    """
    fingerprint = compute_dataset_fingerprint(train_df, test_df, cfg)
    (run_dir / "dataset_fingerprint.json").write_text(json.dumps(fingerprint, indent=2))
    return fingerprint


def write_scorecard(run_dir: Path, scorecard: dict, markdown: str, html: str) -> None:
    (run_dir / "scorecard.json").write_text(json.dumps(scorecard, indent=2))
    (run_dir / "SCORECARD.md").write_text(markdown)
    (run_dir / "SCORECARD.html").write_text(html)


def write_run_status(run_dir: Path, status: str, failed_stage: str | None = None, error: str | None = None) -> None:
    payload = {
        "status": status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "failed_stage": failed_stage,
        "error": error,
    }
    (run_dir / "run_status.json").write_text(json.dumps(payload, indent=2))
