"""Best-effort software version info for cache invalidation and run provenance.

Used by cache.py's fingerprint (so a code change to loading/splitting
logic invalidates an existing cache even when the config and input
files haven't changed) and run_manager.py's environment.json.
"""

from __future__ import annotations

import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def get_version_info() -> dict:
    try:
        pkg_version = version("ids2eval")
    except PackageNotFoundError:
        pkg_version = "unknown (not pip-installed)"

    git_commit = None
    git_path = shutil.which("git")  # resolve full path, not a bare "git" off PATH
    if git_path:
        try:
            result = subprocess.run(  # noqa: S603 - fixed args, no untrusted input
                [git_path, "rev-parse", "HEAD"],
                cwd=Path(__file__).parent,
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass

    return {"version": pkg_version, "git_commit": git_commit}
