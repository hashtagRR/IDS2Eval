#!/usr/bin/env python3
"""Version 0.3.1 additions on the artifacts where version 0.3.0 showed the gaps.

1. Value-specific single-feature statistic. Flood et al.'s single-feature test
   (validation/flood_comparison.py) finds five attack classes that one feature
   separates from benign traffic almost perfectly (F1 >= 0.99) while the raw-value
   AUC of feature_auc_ranking_check misses them: backdoor, injection, password and
   scanning on ToN-IoT's Train_Test_Network.csv and Generic on the UNSW-NB15
   partitions. This reruns feature_auc_ranking_check, which now also reports the
   held-out value-lookup F1 of each class against the reference class, on the
   same training splits the audits used, and lists every class next to Flood's F1.

2. Release-aware known_issue_lookup on the corrected CIC-IDS2017 release: the
   lookup with dataset.release unset (as in version 0.3.0) and set to "corrected".

Writes results/analysis/feature_value_rule.json.

Usage: python3 validation/feature_value_rule.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import yaml

from ids2eval.audit import feature_auc_ranking, known_issues
from ids2eval.config import DEFAULTS, _deep_merge, validate_config
from ids2eval.data import dataset

DATA = Path(os.environ.get("IDS2EVAL_DATA", "/home/tango/projects/IDS2Eval_data"))
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "results" / "configs"
FLOOD = ROOT / "results" / "analysis" / "flood_comparison.json"
OUT = ROOT / "results" / "analysis" / "feature_value_rule.json"
SEPARABLE = 0.99


def load_config(path: Path) -> dict:
    """The archived config, validated, with the scorecard plot off: no scorecard is written here."""
    cfg = _deep_merge(DEFAULTS, yaml.safe_load(path.read_text()) or {})
    cfg["output"]["write_scorecard_plot"] = False
    validate_config(cfg)
    return cfg


def training_split(name: str):
    cfg = load_config(CONFIG_DIR / f"{name}.yaml")
    if name == "ton-iot-official":
        cfg["dataset"]["raw_files"] = [str(DATA / "data/train_test_network.csv.gz")]
    else:
        # this copy is named by content (175,341 training rows), unlike the older mirror
        # with inverted names (paper Section 5.1); the size check below guards the choice
        cfg["dataset"]["train_file"] = str(DATA / "data/UNSW_NB15_training-set.csv.gz")
        cfg["dataset"]["test_file"] = str(DATA / "data/UNSW_NB15_testing-set.csv.gz")
    train, _ = dataset.load_split(cfg)
    if name == "unsw-nb15" and len(train) != 175_341:
        raise RuntimeError(f"unexpected UNSW-NB15 training size {len(train)}")
    return cfg, train


def value_rule_run(name: str, flood: dict) -> dict:
    cfg, train = training_split(name)
    start = time.time()
    result = feature_auc_ranking.check(train, cfg)
    seconds = time.time() - start
    rules = result["details"]["value_rules"]
    flood_f1 = {cls: v.get("flood_f1") for cls, v in flood.get("_class_vs_benign_auc", {}).get(name, {}).items()}
    classes = {}
    for cls, rule in sorted(rules["by_class"].items()):
        f = flood_f1.get(cls)
        classes[cls] = {"feature": rule["feature"], "value_rule_f1": round(rule["f1"], 4),
                        "flood_f1": None if f is None else round(f, 4)}
    flood_cases = sorted(c for c, f in flood_f1.items() if f is not None and f >= SEPARABLE)
    return {
        "training_rows": len(train), "seconds": round(seconds, 1),
        "status": result["status"], "auc_status": result["details"]["auc_status"],
        "value_rule_status": result["details"]["value_rule_status"],
        "reference_class": rules["reference_class"], "reference_source": rules["reference_source"],
        "flood_separable_classes": flood_cases,
        "flood_separable_found": {c: classes.get(c, {}).get("value_rule_f1") for c in flood_cases},
        "by_class": classes, "summary": result["summary"],
    }


def known_issue_runs() -> dict:
    cfg = load_config(CONFIG_DIR / "cic-ids2017-improved-benign.yaml")
    out = {"dataset_name": cfg["dataset"]["name"]}
    for release in (None, "corrected"):
        cfg["dataset"]["release"] = release
        r = known_issues.check(pd.DataFrame(), cfg)
        out[str(release)] = {"status": r["status"], "applicable": len(r["details"]["matches"]),
                             "other_releases": len(r["details"].get("other_releases", [])),
                             "summary": r["summary"]}
    return out


def main() -> None:
    flood = json.loads(FLOOD.read_text())
    report = {"value_rule": {name: value_rule_run(name, flood) for name in ("ton-iot-official", "unsw-nb15")},
              "known_issue_lookup": known_issue_runs()}
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    for name, r in report["value_rule"].items():
        print(name, r["status"], "| AUC", r["auc_status"], "| value rule", r["value_rule_status"],
              "| reference", r["reference_class"], f"| {r['seconds']} s")
        for cls, f1 in r["flood_separable_found"].items():
            print(f"  Flood case {cls}: value-rule F1 {f1} ({r['by_class'][cls]['feature']}),"
                  f" Flood F1 {r['by_class'][cls]['flood_f1']}")
    for k in ("None", "corrected"):
        r = report["known_issue_lookup"][k]
        print("known_issue_lookup release", k, r["status"], "applicable", r["applicable"], "other", r["other_releases"])
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
