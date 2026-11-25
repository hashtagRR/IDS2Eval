#!/usr/bin/env python3
"""homogeneity_test with a host-cluster interval on real datasets.

Runs the check as released on the audit's random 80/20 split, before and after
deduplication, with audit.homogeneity_cluster_columns set to the source host,
and lists per class the default (Newcombe) interval and verdict next to the
host-cluster bootstrap interval and verdict, and whether they agree.

Run from the directory that holds data/.

Usage: python3 validation/homogeneity_real_clusters.py OUT_JSON DATASET [DATASET ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grouping_keys import config_path, load_analysis_config

from ids2eval.audit import homogeneity
from ids2eval.data import dataset

HOST = {"ton-iot-official": "src_ip", "bot-iot-official": "saddr", "cic-ids2017-glf": "Source IP",
        "cic-ids2017-improved-benign": "Src IP", "ctu13-coarse": "SrcAddr"}


def main() -> None:
    out = Path(sys.argv[1])
    results = json.loads(out.read_text()) if out.exists() else {}
    for name in sys.argv[2:]:
        path = config_path(name)
        if path.stem in results:
            continue
        cfg = load_analysis_config(path)
        cfg["audit"]["homogeneity_cluster_columns"] = [HOST[path.stem]]
        train, test = dataset.load_split(cfg)
        entry = {"cluster_column": HOST[path.stem]}
        for stage in ("before_dedup", "after_dedup"):
            if stage == "after_dedup":
                train, test, _ = dataset.dedup(train, test, cfg)
            per_class = homogeneity.check(train, test, cfg)["details"]["per_class"]
            entry[stage] = {
                str(c): {"row_ci": v["row_ci_95"], "row": v["classification"],
                         "cluster_ci": v["cluster_ci_95"], "cluster": v["cluster_classification"],
                         "agree": v["classification"] == v["cluster_classification"]}
                for c, v in per_class.items()
            }
            changed = {c: (v["row"], v["cluster"]) for c, v in entry[stage].items() if not v["agree"]}
            print(path.stem, stage, f"{len(per_class)} classes, verdict changes: {changed}", flush=True)
        results[path.stem] = entry
        out.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
