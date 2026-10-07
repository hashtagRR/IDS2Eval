#!/usr/bin/env python3
"""Re-scores identity_column_flag on the real datasets with the training-only
lookup method, before and after deduplication, on the same splits the paper's
audits used.

Memory-lean so it runs on a small VM: each split is streamed in parquet record
batches and reduced to a 64-bit hash of the columns dataset.dedup compares,
plus the identifier, label and attack-category columns. Deduplication is then
done on the hashes with dataset.dedup's exact order of operations (train
duplicates, then test rows matching train, then test duplicates), and the
resulting counts are printed next to the stored ones so any mismatch shows.

Sources: a local audit cache (output/<name>/.cache/{train,test}.parquet), or
for cic-ids2018-fullscale the batch run's cached combined frame, split again
with the audit's own random split (seed and stratification from the config).

Usage: venv/bin/python3 validation/identity_rerun.py NAME [NAME ...]
       NAME=cic-ids2018-fullscale:/path/to/combined.parquet for the batch cache
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.model_selection import train_test_split

from ids2eval.audit import identity_columns
from ids2eval.config import load_config

DATA = Path("/home/tango/projects/IDS2Eval_data")
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "identity_lookup.json"


def reduce_parquet(path, cfg):
    """Hash of the dedup comparison columns, plus the columns the check needs."""
    schema = cfg["schema"]
    keep = list(dict.fromkeys(schema["id_like_columns"] + [schema["label_column"]]
                              + ([schema["attack_category_column"]] if schema["attack_category_column"] else [])))
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    pf = pq.ParquetFile(path)
    compare = [c for c in pf.schema_arrow.names if c not in ignore]
    parts = []
    for batch in pf.iter_batches(batch_size=500_000):
        df = batch.to_pandas()
        part = df[[c for c in keep if c in df.columns]].copy()
        part["_h"] = pd.util.hash_pandas_object(df[compare], index=False).to_numpy()
        for c in part.columns:
            if part[c].dtype == object or str(part[c].dtype).startswith("str"):
                part[c] = part[c].astype("category")
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def dedup_by_hash(train, test):
    n_train_dupe = int(train["_h"].duplicated().sum())
    train = train.drop_duplicates("_h").reset_index(drop=True)
    leak = test["_h"].isin(set(train["_h"]))
    n_leak = int(leak.sum())
    test = test.loc[~leak.to_numpy()].reset_index(drop=True)
    n_test_dupe = int(test["_h"].duplicated().sum())
    test = test.drop_duplicates("_h").reset_index(drop=True)
    return train, test, {"train_duplicates_dropped": n_train_dupe, "test_leakage_dropped": n_leak,
                         "test_duplicates_dropped": n_test_dupe, "train_rows_deduped": len(train),
                         "test_rows_deduped": len(test)}


def score(train, test, cfg):
    r = identity_columns.check_predictive_power(train, test, cfg)
    d = r["details"]
    return {"status": r["status"], "standalone_auc": d["standalone_auc"], "seen_only_auc": d["seen_only_auc"],
            "seen_coverage": d["seen_coverage"], "suggested_drop": d["suggested_drop"],
            "by_class": d.get("by_class", {})}


def main():
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for arg in sys.argv[1:]:
        name, _, combined_path = arg.partition(":")
        cfg_name = "cic-ids2018-fullscale" if combined_path else name
        cfg = load_config(str(DATA / "configs" / f"{cfg_name}.yaml"))
        if combined_path:
            full = reduce_parquet(combined_path, cfg)
            label = cfg["schema"]["label_column"]
            idx = np.arange(len(full))
            tr_idx, te_idx = train_test_split(idx, test_size=1.0 - cfg["dataset"]["split_ratio"],
                                              random_state=cfg["random_seed"], stratify=full[label])
            train, test = full.iloc[tr_idx].reset_index(drop=True), full.iloc[te_idx].reset_index(drop=True)
            del full
        else:
            cache = DATA / "output" / name / ".cache"
            train, test = reduce_parquet(cache / "train.parquet", cfg), reduce_parquet(cache / "test.parquet", cfg)
        entry = {"train_rows": len(train), "test_rows": len(test), "before": score(train, test, cfg)}
        train, test, stats = dedup_by_hash(train, test)
        entry["dedup"] = stats
        entry["after"] = score(train, test, cfg)
        results[name] = entry
        OUT.write_text(json.dumps(results, indent=2))
        print(f"=== {name}: train {entry['train_rows']:,} test {entry['test_rows']:,} dedup {stats}", flush=True)
        for stage in ("before", "after"):
            e = entry[stage]
            print(f"  {stage}: {e['status']} " + "; ".join(
                f"{c} AUC {e['standalone_auc'][c]:.3f} cov {e['seen_coverage'][c]:.1%} seen-AUC "
                f"{(e['seen_only_auc'][c] or float('nan')):.3f}" for c in e["standalone_auc"]), flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
