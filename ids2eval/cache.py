"""Cache the expensive part of the pipeline: raw load + split + label grouping.

Deliberately caches BEFORE dedup, not after: dedup_check needs to see
real, pre-cleanup duplication (see audit/__init__.py's run_audit
docstring), so a cache boundary placed after dedup would silently make
dedup_check report zero on every cache hit. Scaling and sampling are
NOT cached here - they run on an already-capped sample (max_rows /
MAX_FIT_ROWS) and take seconds, not minutes, so caching them buys
little while adding staleness risk against config people iterate on
constantly (preprocessing.scaling/sampling, classifiers.*).

Stored under output.dir/.cache/, separate from the user-facing
train.<fmt>/test.<fmt> written by output.save_preprocessed (those
represent the final, post-dedup data for external use - a different
artifact from this internal load-skip cache).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import pandas as pd

from . import version_info

logger = logging.getLogger(__name__)

CACHE_DIRNAME = ".cache"
MANIFEST_NAME = "manifest.json"


def _input_file_stats(paths: list[str]) -> list[dict]:
    stats = []
    for path in paths:
        try:
            st = os.stat(path)
            stats.append({"path": str(Path(path).resolve()), "size": st.st_size, "mtime": st.st_mtime})
        except FileNotFoundError:
            stats.append({"path": str(Path(path).resolve()), "size": None, "mtime": None})
    return stats


def compute_fingerprint(cfg: dict) -> str:
    dataset_cfg = cfg["dataset"]
    input_paths = dataset_cfg["raw_files"] or [dataset_cfg["train_file"], dataset_cfg["test_file"]]

    fingerprint_input = {
        "input_files": _input_file_stats(sorted(p for p in input_paths if p)),
        "random_seed": cfg["random_seed"],
        "split_ratio": dataset_cfg["split_ratio"],
        "split_mode": dataset_cfg["split_mode"],
        "group_columns": dataset_cfg["group_columns"],
        "chunk_size": dataset_cfg["chunk_size"],
        "max_rows": dataset_cfg["max_rows"],
        "label_column": cfg["schema"]["label_column"],
        "attack_category_column": cfg["schema"]["attack_category_column"],
        "drop_columns": cfg["schema"]["drop_columns"],
        "attack_type_mapping": cfg["label_grouping"]["attack_type_mapping"],
        "ids2eval_version": version_info.get_version_info(),
    }
    encoded = json.dumps(fingerprint_input, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def try_load(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Return (train_df, test_df) from a valid cache, or None on a miss."""
    cache_dir = Path(cfg["output"]["dir"]) / CACHE_DIRNAME
    manifest_path = cache_dir / MANIFEST_NAME
    train_path, test_path = cache_dir / "train.parquet", cache_dir / "test.parquet"

    if not (manifest_path.exists() and train_path.exists() and test_path.exists()):
        return None

    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    if manifest.get("fingerprint") != compute_fingerprint(cfg):
        logger.info("Cache found but stale (config or input files changed) - reprocessing")
        return None

    logger.info("Loading train/test from cache at %s (skips raw load + split + label grouping)", cache_dir)
    return pd.read_parquet(train_path), pd.read_parquet(test_path)


def save(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> None:
    cache_dir = Path(cfg["output"]["dir"]) / CACHE_DIRNAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_parquet(cache_dir / "train.parquet", index=False)
    test_df.to_parquet(cache_dir / "test.parquet", index=False)
    manifest = {"fingerprint": compute_fingerprint(cfg)}
    (cache_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
    logger.info("Cached load+split+label-grouping result to %s", cache_dir)
