"""JSON-file checkpoint for resuming a long audit run after a crash.

Exists for full-scale runs on Cloud Batch, where a preemption/retry starts a
FRESH VM instance - anything checkpointed only to that VM's local disk is
lost regardless of in-process logic. This module only handles the local
read/write side; surviving an actual VM-level retry additionally requires
the caller (the batch runner script) to sync the checkpoint directory
to/from a durable location (GCS) around the run - this module doesn't know
about that, it just needs a stable local path across separate process runs.

Two granularities:
- Whole-check: run_audit() skips recomputing a check entirely if its finding
  is already checkpointed.
- Per-seed, repeated_seed_falsification_check only: that check alone can
  dominate a full-scale run's cost (it's N independent full refits), so a
  crash partway through its seed loop should only cost the remaining seeds,
  not the whole check.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .._json_utils import json_default


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _atomic_write(path: str, data: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, default=json_default))
    os.replace(tmp, p)


def get_check(path: str, check_name: str) -> dict | None:
    return load(path).get("checks", {}).get(check_name)


def save_check(path: str, check_name: str, finding: dict) -> None:
    data = load(path)
    data.setdefault("checks", {})[check_name] = finding
    _atomic_write(path, data)


def get_seed_progress(path: str, check_name: str) -> dict[int, float]:
    raw = load(path).get("partial", {}).get(check_name, {}).get("drops_by_seed", {})
    return {int(k): v for k, v in raw.items()}


def save_seed_progress(path: str, check_name: str, seed: int, drop: float) -> None:
    data = load(path)
    partial = data.setdefault("partial", {}).setdefault(check_name, {"drops_by_seed": {}})
    partial["drops_by_seed"][str(seed)] = drop
    _atomic_write(path, data)


def clear(path: str) -> None:
    """Remove the checkpoint after a run completes successfully, so a later
    fresh run of the same config doesn't silently resume stale progress."""
    p = Path(path)
    if p.exists():
        p.unlink()
