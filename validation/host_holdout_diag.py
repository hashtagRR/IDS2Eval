#!/usr/bin/env python3
"""Diagnostics for the host-disjoint cross-validation (host_holdout.py).

A host-disjoint fold can lose accuracy for reasons other than a model having
learned host identity: a class confined to a few hosts loses most of its
training rows when those hosts are held out, a source-host fold can still
contain its held-out hosts as destinations, and identifier values never seen
in training are encoded as missing. For each dataset this records, on the
same 5-fold designs and reference model as host_holdout.py (seed 0):

  hosts        distinct source and destination hosts overall and per class,
               and the share of each class's rows that its largest source
               host contributes
  folds        per fold and class: training rows, training hosts, test rows,
               test hosts; per-fold accuracy, balanced accuracy, macro-F1
               and class recall, identifiers kept and dropped
  overlap      for the source-host design, test-fold source hosts that occur
               in the training fold as destinations, and the reverse for the
               destination-host design
  endpoint     a fully endpoint-disjoint design: rows grouped by the
               connected component of the source-destination host graph; if
               one component holds most rows the design is infeasible and
               the component sizes are reported instead
  clustered    95% percentile bootstrap over held-out hosts (2,000 draws) of
               the accuracy difference between random and host-disjoint
               out-of-fold predictions on the same rows
  unseen_ids   per fold, the share of test rows whose identifier values never
               occur in the training fold, and the confusion counts of each
               class with identifiers kept and dropped (the encoding sends
               unseen values to the missing-value branch)

Model selection is not part of this design: the reference model has fixed
hyperparameters, and the encoder and the training sample are fitted inside
each training fold only.

Usage: venv/bin/python3 validation/host_holdout_diag.py NAME [NAME ...]
"""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import host_holdout as hh  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, recall_score  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold  # noqa: E402

from ids2eval.config import load_config  # noqa: E402
from ids2eval.data import dataset  # noqa: E402

SEED = 0
B = 2000
GIANT = 0.5  # a component holding more than this share of rows makes endpoint-disjoint folds infeasible
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "host_holdout_diag.json"


def components(src, dst):
    """Connected components of the bipartite-free host graph (an edge per row)."""
    hosts = pd.Index(pd.unique(np.concatenate([src, dst])))
    parent = np.arange(len(hosts))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in zip(hosts.get_indexer(src), hosts.get_indexer(dst)):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([find(i) for i in range(len(hosts))])
    return roots[hosts.get_indexer(src)]


def fold_metrics(y, pred, labels):
    rec = recall_score(y, pred, labels=labels, average=None, zero_division=0)
    return {"accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
            "recall": {str(c): float(r) for c, r in zip(labels, rec)}}


def run_design(df, y, label_col, cfg, splitter, groups, id_cols, src, dst, other_role):
    labels = sorted(np.unique(y))
    preds = {v: np.empty(len(df), dtype=object) for v in hh.VARIANTS}
    folds = []
    for k, (tr, te) in enumerate(splitter.split(df, y, groups)):
        f = {"fold": k, "test_rows": int(len(te)), "per_class": {}}
        for c in labels:
            trc, tec = tr[y[tr] == c], te[y[te] == c]
            f["per_class"][str(c)] = {
                "train_rows": int(len(trc)), "test_rows": int(len(tec)),
                "train_src_hosts": int(len(set(src[trc]))), "test_src_hosts": int(len(set(src[tec]))),
                "train_dst_hosts": int(len(set(dst[trc]))), "test_dst_hosts": int(len(set(dst[tec])))}
        if groups is not None:
            test_hosts = set(groups[te])
            other_train = set((dst if other_role == "dst" else src)[tr])
            f["held_out_hosts"] = int(len(test_hosts))
            f["held_out_hosts_seen_in_training_in_other_role"] = int(len(test_hosts & other_train))
        f["unseen_id_share"] = {}
        for col in id_cols:
            seen = set(df[col].iloc[tr].astype(str))
            f["unseen_id_share"][col] = float((~df[col].iloc[te].astype(str).isin(seen)).mean())
        for v in hh.VARIANTS:
            p = hh.fold_predict(df, tr, te, label_col, cfg, SEED, v == "ids_dropped")
            preds[v][te] = p
            f[v] = fold_metrics(y[te], p.astype(y.dtype), labels)
        folds.append(f)
        gc.collect()
    pooled = {v: fold_metrics(y, preds[v].astype(y.dtype), labels) for v in hh.VARIANTS}
    confusion = {v: pd.crosstab(pd.Series(y, name="true"), pd.Series(preds[v].astype(y.dtype), name="pred"))
                 .to_dict(orient="index") for v in hh.VARIANTS}
    return folds, pooled, confusion, preds


def clustered_ci(y, pred_random, pred_host, groups, rng):
    ok_r = (pred_random == y).astype(float)
    ok_h = (pred_host == y).astype(float)
    g = pd.Series(groups).astype("category").cat.codes.to_numpy()
    n = np.bincount(g)
    dr = np.bincount(g, weights=ok_r)
    dh = np.bincount(g, weights=ok_h)
    k = len(n)
    draws = rng.multinomial(k, np.full(k, 1 / k), size=B)
    diff = (draws @ dr - draws @ dh) / (draws @ n)
    point = float((ok_r.sum() - ok_h.sum()) / len(y))
    lo, hi = np.percentile(diff, [2.5, 97.5])
    return {"difference": point, "ci_95": [float(lo), float(hi)], "clusters": int(k)}


def main():
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for name in sys.argv[1:]:
        if name in results:
            print(f"skip {name} (done)", flush=True)
            continue
        spec = hh.DATASETS[name]
        cfg = load_config(str(hh.CONFIG_DIR / f"{name}.yaml"))
        cfg["dataset"]["raw_files"] = [str(spec["raw"])]
        label_col = cfg["schema"]["label_column"]
        df = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"]).reset_index(drop=True)
        y = df[label_col].to_numpy()
        scol, dcol = spec["hosts"]["source_host"], spec["hosts"]["destination_host"]
        src, dst = df[scol].astype(str).to_numpy(), df[dcol].astype(str).to_numpy()
        id_cols = [c for c in (cfg["schema"].get("id_like_columns") or []) if c in df.columns]
        print(f"=== {name}: {len(df):,} rows, {len(set(src))} source hosts, {len(set(dst))} destination hosts", flush=True)

        entry = {"rows": int(len(df)), "source_hosts": int(len(set(src))), "destination_hosts": int(len(set(dst))),
                 "id_columns": id_cols, "per_class_hosts": {}}
        for c in sorted(np.unique(y)):
            m = y == c
            top = pd.Series(src[m]).value_counts()
            entry["per_class_hosts"][str(c)] = {
                "rows": int(m.sum()), "src_hosts": int(len(top)), "dst_hosts": int(len(set(dst[m]))),
                "top_src_host_share": float(top.iloc[0] / m.sum())}

        comp = components(src, dst)
        sizes = pd.Series(comp).value_counts()
        entry["endpoint_components"] = {"count": int(len(sizes)), "largest_share": float(sizes.iloc[0] / len(df)),
                                        "largest_sizes": [int(x) for x in sizes.iloc[:10]]}

        designs = {"random": (StratifiedKFold(hh.N_FOLDS, shuffle=True, random_state=SEED), None, None),
                   "source_host": (StratifiedGroupKFold(hh.N_FOLDS, shuffle=True, random_state=SEED), src, "dst"),
                   "destination_host": (StratifiedGroupKFold(hh.N_FOLDS, shuffle=True, random_state=SEED), dst, "src")}
        if entry["endpoint_components"]["largest_share"] <= GIANT and len(sizes) >= hh.N_FOLDS:
            designs["endpoint_disjoint"] = (StratifiedGroupKFold(hh.N_FOLDS, shuffle=True, random_state=SEED),
                                            comp.astype(str), None)
        else:
            entry["endpoint_disjoint_infeasible"] = (
                f"largest connected component of the host graph holds {sizes.iloc[0] / len(df):.1%} of rows")

        preds = {}
        entry["designs"] = {}
        for dname, (splitter, groups, other) in designs.items():
            print(f"  design {dname}", flush=True)
            folds, pooled, confusion, p = run_design(df, y, label_col, cfg, splitter, groups, id_cols, src, dst, other)
            entry["designs"][dname] = {"folds": folds, "pooled": pooled, "confusion": confusion}
            preds[dname] = p
            print(f"    pooled accuracy kept {pooled['ids_kept']['accuracy']:.4f} dropped {pooled['ids_dropped']['accuracy']:.4f}", flush=True)

        rng = np.random.default_rng(SEED)
        entry["clustered"] = {}
        for dname, (_, groups, _) in designs.items():
            if groups is None:
                continue
            entry["clustered"][dname] = {
                v: clustered_ci(y, preds["random"][v].astype(y.dtype), preds[dname][v].astype(y.dtype), groups, rng)
                for v in hh.VARIANTS}
        results[name] = entry
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2, default=str))
        del df
        gc.collect()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
