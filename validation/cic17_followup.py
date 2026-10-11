#!/usr/bin/env python3
"""Follow-up analyses for the corrected CIC-IDS2017 case study (paper Section 5).

Four parts, each written to the output JSON as soon as it finishes, so a
resumed run skips what is already there:

  dedup        feature-vector duplication on the corrected release with the
               address columns kept (as audited) and without Src IP, Dst IP
               and Src Port, which matches the original MachineLearningCSV
               release (destination port only); same split and dedup as
               the audit
  class_seeds  random versus 5-tuple-grouped split over 10 paired seeds:
               accuracy, balanced accuracy, macro-F1 and per-class recall
               with support (validation/class_sensitive_seeds.py's method)
  id_ablation  reference-model accuracy, balanced accuracy and macro-F1 with
               all features, without the two address columns, without the
               two port columns, and without all four; random split,
               seeds 0-4
  initwin_auc  standalone one-vs-rest AUC of each initial-window column for
               every class (feature_auc_ranking_check's statistic: rank AUC,
               either direction), on the training partition of the seed-0
               random split, for the corrected release and for the original
               MachineLearningCSV release

Run from the directory that holds data/; configs are read from
results/configs/ in this repository.

Usage: python3 validation/cic17_followup.py OUT_JSON
"""
from __future__ import annotations

import gc
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import yaml
from class_sensitive_seeds import score, summarize
from scipy.stats import rankdata
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from ids2eval.config import load_config
from ids2eval.data import dataset, features

REPO = Path(__file__).resolve().parent.parent
CONFIGS = REPO / "results" / "configs"
MAX_FIT_ROWS = 200_000
N_SEEDS = int(os.environ.get("CIC17_FOLLOWUP_SEEDS", "10"))  # smaller only for a smoke test
ABLATION_SEEDS = range(int(os.environ.get("CIC17_FOLLOWUP_ABLATION_SEEDS", "5")))
ADDRESSES = ["Src IP", "Dst IP"]
PORTS = ["Src Port", "Dst Port"]
INITWIN = {"corrected": ["FWD Init Win Bytes", "Bwd Init Win Bytes"],
           "original": ["Init_Win_bytes_forward", "Init_Win_bytes_backward"]}


def load_cfg(name):
    """An archived config, loaded with output.write_scorecard_plot off: the plot needs
    matplotlib, which this analysis does not use and the batch environment lacks."""
    raw = yaml.safe_load((CONFIGS / name).read_text())
    raw.setdefault("output", {})["write_scorecard_plot"] = False
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(raw, f)
    return load_config(f.name)


def corrected_cfg():
    return load_cfg("cic-ids2017-improved.yaml")


def save(out, results):
    out.write_text(json.dumps(results, indent=2))


def part_dedup():
    res = {}
    for name, extra in (("addresses_kept", []), ("no_addresses", ["Src IP", "Dst IP", "Src Port"])):
        cfg = corrected_cfg()
        cfg["schema"]["drop_columns"] = list(cfg["schema"]["drop_columns"]) + extra
        train, test = dataset.load_split(cfg)
        _, _, stats = dataset.dedup(train, test, cfg)
        stats = {k: int(v) for k, v in stats.items()}
        stats["train_duplicate_rate"] = stats["train_duplicates_dropped"] / stats["train_rows_raw"]
        stats["test_reuse_rate"] = stats["test_leakage_dropped"] / stats["test_rows_raw"]
        res[name] = stats
        print(name, {k: stats[k] for k in ("train_duplicate_rate", "test_reuse_rate")}, flush=True)
        del train, test
        gc.collect()
    return res


def part_class_seeds(results, out):
    cfg = corrected_cfg()
    label = cfg["schema"]["label_column"]
    entry = results.setdefault("class_seeds", {"seeds": []})
    if len(entry["seeds"]) >= N_SEEDS:
        return
    combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
    for seed in range(len(entry["seeds"]), N_SEEDS):
        tr, te = dataset._random_split(combined, label, cfg["dataset"], seed=seed)
        r = score(tr, te, label, cfg, seed)
        del tr, te
        tr, te = dataset._grouped_split(combined, label, cfg["dataset"], seed=seed)
        g = score(tr, te, label, cfg, seed)
        del tr, te
        gc.collect()
        entry["seeds"].append({"seed": seed, "random": r, "grouped": g})
        entry["summary"] = summarize(entry["seeds"])
        save(out, results)
        print(f"class_seeds seed {seed}: macro_f1 {r['macro_f1']:.4f} -> {g['macro_f1']:.4f}", flush=True)


def fit_metrics(train, test, cols, label, seed):
    fit = train.sample(n=min(len(train), MAX_FIT_ROWS), random_state=seed)
    x_fit, x_test = features.encode_aligned(fit, test, cols, unseen="missing")
    clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1).fit(x_fit, fit[label])
    pred = clf.predict(x_test)
    y = test[label]
    return {"accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0))}


def part_id_ablation(results, out):
    cfg = corrected_cfg()
    label = cfg["schema"]["label_column"]
    entry = results.setdefault("id_ablation", {"seeds": []})
    if len(entry["seeds"]) >= len(ABLATION_SEEDS):
        return
    combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
    for seed in ABLATION_SEEDS[len(entry["seeds"]):]:
        tr, te = dataset._random_split(combined, label, cfg["dataset"], seed=seed)
        cols = features.feature_columns(tr, cfg)
        row = {"seed": seed}
        for name, drop in (("all_features", []), ("no_addresses", ADDRESSES), ("no_ports", PORTS),
                           ("no_identifiers", ADDRESSES + PORTS)):
            row[name] = fit_metrics(tr, te, [c for c in cols if c not in drop], label, seed)
        del tr, te
        gc.collect()
        entry["seeds"].append(row)
        save(out, results)
        accs = ", ".join(f"{k} {v['accuracy']:.4f}" for k, v in row.items() if k != "seed")
        print(f"id_ablation seed {seed}: {accs}", flush=True)


def auc_by_class(values, labels):
    """One-vs-rest rank AUC per class, max(AUC, 1 - AUC), as feature_auc_ranking_check computes it."""
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        return None
    classes, codes = np.unique(labels.to_numpy(), return_inverse=True)
    n = len(values)
    n_pos = np.bincount(codes, minlength=len(classes)).astype(float)
    rank_sum = np.bincount(codes, weights=rankdata(values), minlength=len(classes))
    out = {}
    for i, cls in enumerate(classes):
        if 0 < n_pos[i] < n:
            auc = (rank_sum[i] - n_pos[i] * (n_pos[i] + 1) / 2) / (n_pos[i] * (n - n_pos[i]))
            out[str(cls)] = {"auc": float(max(auc, 1 - auc)), "train_rows": int(n_pos[i])}
    return out


def part_initwin_auc():
    res = {}
    for release, cfg_name in (("corrected", "cic-ids2017-improved.yaml"), ("original", "cic-ids2017.yaml")):
        cfg = load_cfg(cfg_name)
        label = cfg["schema"]["label_column"]
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        tr, _ = dataset._random_split(combined, label, cfg["dataset"], seed=cfg["random_seed"])
        res[release] = {"train_rows": len(tr),
                        "columns": {c: auc_by_class(pd.to_numeric(tr[c], errors="coerce").fillna(-2), tr[label])
                                    for c in INITWIN[release]}}
        for c, by in res[release]["columns"].items():
            top = sorted(by.items(), key=lambda kv: -kv[1]["auc"])[:3] if by else []
            print(release, c, [(k, round(v["auc"], 3), v["train_rows"]) for k, v in top], flush=True)
        del combined, tr
        gc.collect()
    return res


def main():
    out = Path(sys.argv[1])
    results = json.loads(out.read_text()) if out.exists() else {}
    if "dedup" not in results:
        results["dedup"] = part_dedup()
        save(out, results)
    if "initwin_auc" not in results:
        results["initwin_auc"] = part_initwin_auc()
        save(out, results)
    part_id_ablation(results, out)
    part_class_seeds(results, out)
    save(out, results)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
