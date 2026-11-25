#!/usr/bin/env python3
"""grouping_keys.py without the reference model's 200,000-row training cap.

The reference model fits on at most 200,000 training rows (ids2eval.audit.
_fit_score.MAX_FIT_ROWS). On CIC-IDS2017 the cap lowers balanced accuracy
itself (validation/cap_sensitivity.py), so a class-sensitive verdict at the cap
may understate a class-level effect. This script reruns the 10-seed grouped
resplit of grouping_keys.py with every training row used, for the keys named.

Run from the directory that holds data/.

Usage: python3 validation/uncapped_keys.py OUT_JSON DATASET KEY [KEY ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import grouping_keys

from ids2eval.audit import _fit_score


def main() -> None:
    out, name, keys = sys.argv[1], sys.argv[2], sys.argv[3:]
    _fit_score.MAX_FIT_ROWS = 10**12
    stem = grouping_keys.config_path(name).stem
    grouping_keys.KEYS[stem] = {k: v for k, v in grouping_keys.KEYS[stem].items() if k in keys}
    sys.argv = [sys.argv[0], out, name]
    grouping_keys.main()


if __name__ == "__main__":
    main()
