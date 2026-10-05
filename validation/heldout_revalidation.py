#!/usr/bin/env python3
"""Re-validation after the sampling-margin fix to resplit_falsification and
result_robustness_check, on fresh seeds the fix was never run against.

Reuses heldout_validation.py's generators and clean-dataset builder with new
seed ranges: part 1 for the three accuracy-based falsification checks
(seeds 300-304), part 2 for the full suite on 30 clean datasets (seeds 300-309
per class balance).

Usage: venv/bin/python3 validation/heldout_revalidation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import heldout_validation as hv

OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "heldout_revalidation.json"
CHECKS = ("resplit_falsification", "repeated_seed_falsification_check", "result_robustness_check")


def main() -> None:
    hv.SEEDS = range(300, 305)
    hv.GENERATORS = {c: hv.GENERATORS[c] for c in CHECKS}
    results = {"part1": hv.part1()}
    OUT.write_text(json.dumps(results, indent=2))
    results["part2"] = hv.part2(range(300, 310))
    OUT.write_text(json.dumps(results, indent=2))
    p2 = results["part2"]
    print(f"clean datasets with any flag: {p2['datasets_with_any_flag']}/{p2['n_datasets']}")
    print("DONE")


if __name__ == "__main__":
    main()
