#!/usr/bin/env python3
"""Head-to-head on identical artifacts: IDS2Eval vs. Flood et al.'s released heuristics.

Flood et al. (2024) release their heuristic tool (github.com/DataBadSmells/
DataBadSmells, commit 88f3278). Three of its tests overlap IDS2Eval checks:

  Flood CosineTest                 repetitiveness: share of sampled same-cluster
                                   flow pairs with cosine similarity > 0.95
  Flood SingleFeatureEfficacyTest  a 20-tree random forest on each single
                                   feature, attack class vs benign, F1
  Flood NearestNeighboursTest      share of attack flows whose nearest
                                   neighbours are mostly benign (mislabel smell)
  Flood PortTest (ToN-IoT only)    share of attack flows to background ports

against, for the same class and artifact,

  dedup_check by class             within-training duplicate rate and the rate
                                   of test rows reusing a training vector
  single-feature AUC by class      feature_auc_ranking_check's statistic
                                   (one-vs-rest AUC of a raw numeric feature,
                                   max(AUC, 1 - AUC)) computed per class
  homogeneity_test                 the class's leakage / cleared verdict
  label_conflict_check             vectors carrying more than one label

Flood's tool pools every CSV it is given, removes exact duplicate rows, and
compares each attack class with benign traffic; IDS2Eval audits a train/test
split. The comparison therefore reports what each tool says about each class,
the agreement on classes one feature separates almost perfectly (Flood F1 >=
0.99; IDS2Eval AUC >= 0.99), and the wall time of each tool on the same
machine. It does not score either tool against a ground truth.

Artifacts: ToN-IoT Train_Test_Network.csv (Flood's own ToN metadata, with drop
fields the file does not contain, such as ts, removed and recorded) and the UNSW-NB15 train/test
partitions (Flood's UNSW metadata
targets the raw capture files, so an adapted copy is used: label attack_cat,
benign "Normal", categorical proto/state/service, id and label dropped; the
partitions have no destination port, so PortTest is skipped and a constant
placeholder port column satisfies the tool's loader).

Usage: venv/bin/python3 validation/flood_comparison.py FLOOD_DIR NAME [NAME ...]
       with a separate interpreter for Flood's tool in FLOOD_PY (default python3)
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from ids2eval.audit import dedup as dedup_mod
from ids2eval.audit import feature_auc_ranking, homogeneity, label_conflict
from ids2eval.config import load_config
from ids2eval.data import dataset, features

DATA = Path(os.environ.get("IDS2EVAL_DATA", "/home/tango/projects/IDS2Eval_data"))
CONFIG_DIR = Path(__file__).resolve().parent.parent / "results" / "configs"
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "flood_comparison.json"
FLOOD_PY = os.environ.get("FLOOD_PY", "python3")
SEPARABLE = 0.99
UNSW_META = {"drop_fields": ["id", "label", "dstport"], "unique_fields": ["proto", "state", "service"],
             "label_field": "attack_cat", "benign_label": "Normal", "dst_port": "dstport", "ignore_ports": []}


def load(name):
    if name == "ton-iot-official":
        cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
        cfg["dataset"]["raw_files"] = [str(DATA / "ton-iot-official/train_test_network.csv.gz")]
        train, test = dataset.load_split(cfg)
        flood_frame = pd.read_csv(DATA / "ton-iot-official/train_test_network.csv.gz")
        meta = None  # Flood's own metadata/ton/metadata.json
        tests = ["CosineTest", "SingleFeatureEfficacyTest", "NearestNeighboursTest", "PortTest"]
    else:
        cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
        # the local mirror's file names are inverted (paper Section 4.2): select by content
        cfg["dataset"]["train_file"] = str(DATA / "unsw-nb15/UNSW_NB15_testing-set.csv")
        cfg["dataset"]["test_file"] = str(DATA / "unsw-nb15/UNSW_NB15_training-set.csv")
        train, test = dataset.load_split(cfg)
        if (len(train), len(test)) != (175_341, 82_332):
            raise RuntimeError(f"unexpected UNSW-NB15 partition sizes {len(train)}, {len(test)}")
        flood_frame = pd.concat([pd.read_csv(cfg["dataset"]["train_file"]),
                                 pd.read_csv(cfg["dataset"]["test_file"])], ignore_index=True)
        flood_frame["dstport"] = 0
        meta = UNSW_META
        tests = ["CosineTest", "SingleFeatureEfficacyTest", "NearestNeighboursTest"]
    return cfg, train, test, flood_frame, meta, tests


def ids2eval_side(cfg, train, test):
    group_col = cfg["schema"]["attack_category_column"] or cfg["schema"]["label_column"]
    timings, out = {}, {}
    t0 = time.time()
    d = dedup_mod.check(train, test, cfg)
    timings["dedup_check"] = time.time() - t0
    t0 = time.time()
    lc = label_conflict.check(train, test, cfg)
    timings["label_conflict_check"] = time.time() - t0
    t0 = time.time()
    fa = feature_auc_ranking.check(train, cfg)
    timings["feature_auc_ranking_check"] = time.time() - t0
    t0 = time.time()
    h = homogeneity.check(train, test, cfg)
    timings["homogeneity_test"] = time.time() - t0

    cols = [c for c in features.feature_columns(train, cfg) if pd.api.types.is_numeric_dtype(train[c])]
    labels = train[group_col].astype(str)
    for cls in sorted(labels.unique()):
        y = (labels == cls).to_numpy()
        best, best_col = 0.0, None
        for c in cols:
            v = train[c].to_numpy(dtype=float)
            ok = ~np.isnan(v)
            if y[ok].all() or not y[ok].any():
                continue
            auc = roc_auc_score(y[ok], v[ok])
            auc = max(auc, 1 - auc)
            if auc > best:
                best, best_col = float(auc), c
        out[cls] = {"best_single_feature": best_col, "best_single_feature_auc": best,
                    "dedup": d["details"]["by_class"].get(cls),
                    "homogeneity": (h["details"]["per_class"].get(cls) or {}).get("classification")}
    return {"timings_s": timings, "statuses": {c["check"]: c["status"] for c in (d, lc, fa, h)},
            "label_conflict_summary": lc["summary"], "per_class": out}


def flood_side(flood_dir, name, frame, meta, tests, benign, label_field):
    work = Path(tempfile.mkdtemp(prefix=f"flood_{name}_"))
    (work / "csv").mkdir()
    frame.to_csv(work / "csv" / "data.csv", index=False)
    if meta is None:
        meta = json.loads((Path(flood_dir) / "metadata" / "ton" / "metadata.json").read_text())
    # the tool raises on a drop field the file lacks; keep only fields present and record the rest
    adapted = dict(meta, drop_fields=[c for c in meta["drop_fields"] if c in frame.columns])
    removed = [c for c in meta["drop_fields"] if c not in frame.columns]
    meta_path = work / "metadata.json"
    meta_path.write_text(json.dumps(adapted))
    classes = sorted(c for c in frame[label_field].astype(str).str.strip().unique() if c != benign)
    per_class, timings = {}, dict.fromkeys(tests, 0.0)
    for cls in classes:
        per_class[cls] = {}
        for t in tests:
            res_dir = work / "results"
            t0 = time.time()
            proc = subprocess.run(  # noqa: S603 - fixed argument list, no shell
                [FLOOD_PY, str(Path(flood_dir) / "src" / "netstats.py"), "--metadata", str(meta_path),
                 "--results", str(res_dir) + "/", "--target", cls, "--folder", "--csv", str(work / "csv") + "/",
                 "--test", t], capture_output=True, text=True, cwd=str(work))
            timings[t] += time.time() - t0
            found = sorted(glob.glob(str(res_dir / cls / "tests" / f"{t}_*.results")))
            if proc.returncode != 0 or not found:
                per_class[cls][t] = {"error": (proc.stderr or proc.stdout)[-400:]}
                continue
            per_class[cls][t] = json.loads(Path(found[-1]).read_text()).get(t)
    return {"timings_s": timings, "per_class": per_class, "rows_given": len(frame),
            "metadata_used": adapted, "drop_fields_absent_from_artifact": removed}


def summarize_class(cls, f, i):
    sfe = (f.get("SingleFeatureEfficacyTest") or {}).get("F1Scores") or {}
    top = max(sfe.items(), key=lambda kv: kv[1]) if sfe else (None, None)
    cos = f.get("CosineTest") or {}
    sizes, cut = cos.get("Cluster Sizes"), cos.get("Cutoff Percentages")
    identical = None
    if sizes and cut:
        shares = [cut.get(str(k + 1), cut.get(k + 1, 0)) for k in range(len(sizes))]
        identical = float(np.average(shares, weights=sizes))
    nn = f.get("NearestNeighboursTest") or {}
    row = {"flood_top_feature": top[0], "flood_top_f1": top[1], "flood_identical_share": identical,
           "flood_largest_cluster_share": cos.get("Largest Cluster Percentage"),
           "flood_nn_mislabel_share": nn.get("Percentage"),
           "flood_port_share": (f.get("PortTest") or {}).get("MislabelPortsPercent")}
    if i:
        row.update({"ids2eval_top_feature": i["best_single_feature"], "ids2eval_top_auc": i["best_single_feature_auc"],
                    "ids2eval_train_dup_rate": (i["dedup"] or {}).get("train_duplicate_rate"),
                    "ids2eval_test_reuse_rate": (i["dedup"] or {}).get("test_leak_rate"),
                    "ids2eval_homogeneity": i["homogeneity"]})
        a = row["flood_top_f1"] is not None and row["flood_top_f1"] >= SEPARABLE
        b = row["ids2eval_top_auc"] >= SEPARABLE
        row["separable_agreement"] = {"flood": a, "ids2eval": b}
    return row


def main():
    flood_dir, names = sys.argv[1], sys.argv[2:]
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for name in names:
        if name in results:
            print(f"skip {name} (done)", flush=True)
            continue
        cfg, train, test, frame, meta, tests = load(name)
        label_field = "type" if meta is None else meta["label_field"]
        benign = "normal" if meta is None else meta["benign_label"]
        print(f"=== {name}: IDS2Eval on {len(train):,}+{len(test):,} rows", flush=True)
        t0 = time.time()
        ours = ids2eval_side(cfg, train, test)
        ours["total_s"] = time.time() - t0
        print(f"  IDS2Eval {ours['total_s']:.0f}s; Flood tool on {len(frame):,} rows", flush=True)
        t0 = time.time()
        theirs = flood_side(flood_dir, name, frame, meta, tests, benign, label_field)
        theirs["total_s"] = time.time() - t0
        print(f"  Flood {theirs['total_s']:.0f}s", flush=True)
        rows = {cls: summarize_class(cls, theirs["per_class"][cls], ours["per_class"].get(cls))
                for cls in theirs["per_class"]}
        both = [r["separable_agreement"] for r in rows.values() if "separable_agreement" in r]
        results[name] = {"ids2eval": ours, "flood": theirs, "per_class": rows,
                         "separable": {"both": sum(a["flood"] and a["ids2eval"] for a in both),
                                       "flood_only": sum(a["flood"] and not a["ids2eval"] for a in both),
                                       "ids2eval_only": sum(a["ids2eval"] and not a["flood"] for a in both),
                                       "neither": sum(not a["flood"] and not a["ids2eval"] for a in both)}}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2, default=str))
        for cls, r in rows.items():
            print("  ", cls, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
