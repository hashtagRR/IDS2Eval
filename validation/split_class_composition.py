#!/usr/bin/env python3
"""Class composition of the paired random and grouped test splits.

Reads the per-class test support that class_sensitive_seeds.py recorded for
every seed and reports, per dataset, the largest difference in any class's
share of the test set between the random and grouped split, and the largest
Jensen-Shannon divergence between the two class distributions.

Usage: venv/bin/python3 validation/split_class_composition.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.spatial.distance import jensenshannon

ANALYSIS = Path(__file__).resolve().parent.parent / "results" / "analysis"


def main() -> None:
    seeds_data = json.loads((ANALYSIS / "class_sensitive_seeds.json").read_text())
    out = {}
    for name, entry in seeds_data.items():
        max_diff, max_jsd = [], []
        for s in entry["seeds"]:
            r, g = s["random"]["per_class_support"], s["grouped"]["per_class_support"]
            classes = sorted(set(r) | set(g))
            pr = np.array([r.get(c, 0) for c in classes], float)
            pg = np.array([g.get(c, 0) for c in classes], float)
            pr, pg = pr / pr.sum(), pg / pg.sum()
            max_diff.append(float(np.abs(pr - pg).max()))
            max_jsd.append(float(jensenshannon(pr, pg, base=2) ** 2))
        out[name] = {"seeds": len(max_diff), "max_abs_class_share_diff": max(max_diff),
                     "max_js_divergence": max(max_jsd)}
        print(name, out[name])
    (ANALYSIS / "split_class_composition.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
