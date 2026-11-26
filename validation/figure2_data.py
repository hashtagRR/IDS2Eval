#!/usr/bin/env python3
"""Collect the intervention effects shown in the paper's Figure 2 into one CSV.

Every row is one intervention on one dataset for one metric: the mean drop in
percentage points (random-split or full-feature score minus the intervened
score; for reuse removal, the score with the reused training rows minus the
score without them), its 95% interval, the verdict against the one-point
threshold (M material, N not material, I inconclusive) and whether the result
carries a class-support caution.

Sources, all under results/:
  analysis/grouping_keys_<dataset>.json     5-tuple, coarse and host keys
  preregistration/ctu13/runs/<key>/         CTU-13, the three pre-registered keys
  analysis/reuse_removal_models_<ds>.json   reuse removal, reference forest
  analysis/cic17_followup_benign.json       corrected CIC-IDS2017 identifier removal

A grouping-key file that is not there yet is skipped, so the CSV can be rebuilt
as runs finish.

Usage: python3 validation/figure2_data.py [OUT_CSV]
"""
from __future__ import annotations

import csv
import glob
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "results"
METRICS = ["accuracy", "balanced_accuracy", "macro_f1"]
VERDICT = {"flag": "M", "ok": "N", "warning": "I"}
KEY_LABEL = {"five_tuple": "5-tuple", "coarse": "coarse key", "host": "source host", "proxy": "proxy key",
             "proxy_without_time": "port and protocol"}
DATASET_LABEL = {
    "ton-iot-official": "ToN-IoT",
    "bot-iot-official": "BoT-IoT",
    "cic-ddos2019-sample": "CICDDoS2019",
    "cic-ids2017-improved-benign": "CIC-IDS2017 (corrected)",
    "cic-ids2017-glf": "CIC-IDS2017 (original)",
    "cic-ids2017": "CIC-IDS2017 (MachineLearningCSV)",
    "cic-ids2018-fullscale": "CSE-CIC-IDS2018",
    "unsw-nb15": "UNSW-NB15",
    "nsl-kdd": "NSL-KDD",
    "ctu13": "CTU-13",
}
# Keys under which one host holds most of a class or of the rows, so the grouped
# split puts most of a class on one side (paper Section 7.3).
CAUTION = {
    ("ton-iot-official", "host"), ("cic-ddos2019-sample", "host"),
    ("cic-ids2017-improved-benign", "coarse"), ("cic-ids2017-improved-benign", "host"),
    ("ctu13", "host"), ("ctu13", "coarse"), ("cic-ids2017-glf", "host"), ("cic-ids2017-glf", "coarse"),
    ("cic-ids2018-fullscale", "proxy_without_time"),
}
T975 = {4: 2.776, 9: 2.262}


def _row(dataset, intervention, metric, mean, lo, hi, verdict, caution=False):
    return {
        "dataset": DATASET_LABEL.get(dataset, dataset), "intervention": intervention, "metric": metric,
        "mean_points": round(100 * mean, 3), "ci_low_points": round(100 * lo, 3),
        "ci_high_points": round(100 * hi, 3), "verdict": verdict, "caution": int(caution),
    }


def _checks(report_path):
    report = json.loads(Path(report_path).read_text())
    items = report["results"] if "results" in report else report
    items = items if isinstance(items, list) else items["checks"]
    return {item["check"]: item for item in items}


def grouping_keys(rows):
    for path in sorted(glob.glob(str(ROOT / "analysis" / "grouping_keys_*.json"))):
        if "uncapped" in path:  # sensitivity rerun without the training cap, reported in the text
            continue
        for dataset, keys in json.loads(Path(path).read_text()).items():
            for key, result in keys.items():
                by_metric = result.get("repeated_seed", {}).get("details", {}).get("by_metric", {})
                for m in METRICS:
                    if m not in by_metric:
                        continue
                    x = by_metric[m]
                    rows.append(_row(dataset, KEY_LABEL.get(key, key), m, x["mean_drop"], *x["ci_95"],
                                     VERDICT[x["verdict"]], (dataset, key) in CAUTION))


def ctu13(rows):
    runs = ROOT / "preregistration" / "ctu13" / "runs"
    for key, label in (("5tuple", "five_tuple"), ("coarse", "coarse"), ("host", "host")):
        after = sorted(runs.glob(f"{key}/runs/*/audit_report_after.json"))[-1]
        check = _checks(after)["repeated_seed_falsification_check"]
        for m in METRICS:
            x = check["details"]["by_metric"][m]
            rows.append(_row("ctu13", KEY_LABEL[label], m, x["mean_drop"], *x["ci_95"],
                             VERDICT[x["verdict"]], ("ctu13", label) in CAUTION))
    before = sorted(runs.glob("5tuple/runs/*/audit_report_before.json"))[-1]
    reuse = _checks(before)["reuse_removal_falsification"]
    for m in METRICS:
        x = reuse["details"]["by_metric"][m]
        rows.append(_row("ctu13", "reuse removal", m, x["mean_difference"], *x["ci_95"], VERDICT[x["verdict"]]))


def reuse_removal(rows):
    for dataset in ("unsw-nb15", "nsl-kdd", "ton-iot-official", "cic-ids2017", "cic-ids2018-fullscale"):
        path = ROOT / "analysis" / f"reuse_removal_models_{dataset}.json"
        if not path.exists():
            continue
        rf = json.loads(path.read_text())[dataset]["rf"]
        for m in METRICS:
            x = rf["details"]["by_metric"][m]
            rows.append(_row(dataset, "reuse removal", m, x["mean_difference"], *x["ci_95"], VERDICT[x["verdict"]]))


def _verdict(lo, hi, threshold=0.01):
    if lo > threshold:
        return "M"
    if hi < threshold:
        return "N"
    return "I"


def identifier_removal(rows):
    seeds = json.loads((ROOT / "analysis" / "cic17_followup_benign.json").read_text())["id_ablation"]["seeds"]
    for m in METRICS:
        drops = [s["all_features"][m] - s["no_identifiers"][m] for s in seeds]
        mean = statistics.mean(drops)
        half = T975[len(drops) - 1] * statistics.stdev(drops) / len(drops) ** 0.5
        rows.append(_row("cic-ids2017-improved-benign", "identifier removal", m, mean, mean - half, mean + half,
                         _verdict(mean - half, mean + half)))


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "analysis" / "figure2_effects.csv"
    rows = []
    grouping_keys(rows)
    ctu13(rows)
    reuse_removal(rows)
    identifier_removal(rows)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
