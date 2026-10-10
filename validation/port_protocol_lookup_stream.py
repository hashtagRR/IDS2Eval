#!/usr/bin/env python3
"""Memory-lean version of port_protocol_lookup.py for the full-scale corpora.

CIC-IDS2018 (16.2M rows) and CICDDoS2019 (70.4M rows) do not fit in memory on
a small VM. The port/protocol check only needs the port, protocol and label
columns, and deduplication only needs to know which rows have equal feature
vectors. So the raw files are streamed through the tool's own chunk reader
(the same cleaning as its loader) and each row is reduced to those three
columns plus a 64-bit hash of the columns dataset.dedup compares.

The frozen check's own result is read from the stored full-scale audit of
the same release (its string coding would not fit in memory here); only the
lookup is recomputed.

Equal rows must hash equally however a chunk was typed, so before hashing
every compare column is put in one canonical form: numeric columns as
float64 (float32 and integer values convert exactly, so equality is
preserved), other columns as strings. Columns that exist in only some files
are present in every chunk as missing values, as they are when the tool
concatenates the files. Deduplication then repeats dataset.dedup's order of
operations on the hashes (training duplicates, then test rows matching
training, then test duplicates), and the counts are printed next to the
paper's Table 6 so any mismatch shows.

Splits: "random" repeats dataset._random_split (same seed, test size and
stratification, on rows in the same order, so the same indices); "files"
uses the release's own train and test files (CICDDoS2019's day split).

Usage: venv/bin/python3 validation/port_protocol_lookup_stream.py NAME
"""
from __future__ import annotations

import copy
import gzip
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ids2eval.audit import identity_columns, port_protocol_shortcut
from ids2eval.config import load_config
from ids2eval.data import chunked_io

DATA = Path(os.environ.get("IDS2EVAL_DATA", "/home/tango/projects/IDS2Eval_data"))  # data root; set on Batch
RESULTS = Path(__file__).resolve().parent.parent / "results"
CONFIGS = RESULTS / "configs"
RUN_DIRS = {"cic-ids2018-fullscale": "cic-ids2018-fullscale", "cic-ddos2019-fullscale-main": "cic-ddos2019-fullscale-main"}
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "port_protocol_lookup.json"

RUNS = {
    "cic-ids2018-fullscale": {
        "split": "random",
        "files": [DATA / "cic-ids2018" / Path(f).name for f in [
            "Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv.gz", "Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv.gz",
            "Friday-16-02-2018_TrafficForML_CICFlowMeter.csv.gz", "Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv.gz",
            "Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv.gz", "Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv.gz",
            "Friday-23-02-2018_TrafficForML_CICFlowMeter.csv.gz", "Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv.gz",
            "Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv.gz", "Friday-02-03-2018_TrafficForML_CICFlowMeter.csv.gz"]],
        # Table 6: train duplicates / train rows, test in-split duplicates, test rows reusing a training vector, test rows
        "table6": {"train_duplicates_dropped": 3_703_769, "train_rows_raw": 12_986_354,
                   "test_duplicates_dropped": 16_229, "test_leakage_dropped": 1_065_936, "test_rows_raw": 3_246_589},
    },
    "cic-ddos2019-fullscale-main": {
        "split": "files",
        "train": [DATA / "cic-ddos2019" / "train-full.csv.gz"],
        "test": [DATA / "cic-ddos2019" / "test-full.csv.gz"],
        "table6": {"train_duplicates_dropped": 2_184_498, "train_rows_raw": 50_063_112,
                   "test_duplicates_dropped": 650_949, "test_leakage_dropped": 244, "test_rows_raw": 20_364_525},
    },
}


def header(path: Path) -> list[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", errors="replace") as f:
        return [c.strip() for c in f.readline().rstrip("\n").split(",")]


def reduce(paths, cfg, chunk_size, all_columns):
    """Stream paths, keep port/protocol/label and a canonical hash per row."""
    schema = cfg["schema"]
    ignore = set(schema["drop_columns"]) | {schema["label_column"]}
    if schema["attack_category_column"]:
        ignore.add(schema["attack_category_column"])
    compare = [c for c in all_columns if c not in ignore]
    port = port_protocol_shortcut._find_column(schema["id_like_columns"], "port")
    proto = port_protocol_shortcut._find_column(all_columns, "proto")
    parts, n = [], 0
    for chunk in chunked_io.iter_chunks([str(p) for p in paths], chunk_size):
        chunk.columns = [c.strip() for c in chunk.columns]
        canon = pd.DataFrame(index=chunk.index)
        for c in compare:
            if c not in chunk.columns:
                canon[c] = np.nan
            elif pd.api.types.is_numeric_dtype(chunk[c]):
                canon[c] = chunk[c].astype("float64")
            else:
                canon[c] = chunk[c].astype(str)
        part = pd.DataFrame({"_h": pd.util.hash_pandas_object(canon, index=False).to_numpy()})
        # One numeric key per row, port * 256 + protocol (exact: protocol numbers are
        # below 256), so the lookup compares numbers; strings for 70M rows would not fit.
        port_v = pd.to_numeric(chunk[port], errors="coerce").to_numpy(dtype="float64")
        proto_v = pd.to_numeric(chunk[proto], errors="coerce").to_numpy(dtype="float64")
        part["_key"] = port_v * 256 + proto_v
        # .to_numpy(): chunks keep their original row index (200,000 onward for the
        # second chunk) while `part` starts at 0, so assigning a Series would align
        # on the index and leave every later chunk's labels missing.
        part[schema["label_column"]] = pd.Categorical(chunk[schema["label_column"]].to_numpy())
        parts.append(part)
        n += len(chunk)
        if len(parts) % 20 == 0:
            print(f"    {n:,} rows reduced", flush=True)
    out = pd.concat(parts, ignore_index=True)
    out[schema["label_column"]] = out[schema["label_column"]].astype(str).astype("category")
    return out, port, proto


def dedup(train, test):
    n_train0, n_test0 = len(train), len(test)
    train_dupe = train["_h"].duplicated()
    train = train.loc[~train_dupe].reset_index(drop=True)
    leak = test["_h"].isin(set(train["_h"]))
    test = test.loc[~leak].reset_index(drop=True)
    test_dupe = test["_h"].duplicated()
    test = test.loc[~test_dupe].reset_index(drop=True)
    return train, test, {"train_rows_raw": n_train0, "train_duplicates_dropped": int(train_dupe.sum()),
                         "test_rows_raw": n_test0, "test_leakage_dropped": int(leak.sum()),
                         "test_duplicates_dropped": int(test_dupe.sum())}


def frozen_result(name, stage):
    """The frozen check's stored result from the full-scale batch audit of this release."""
    run = sorted((RESULTS / "batch_audit_runs" / RUN_DIRS[name]).glob("**/runs/*/audit_report_" + stage + ".json"))[-1]
    return next(r for r in json.loads(run.read_text()) if r["check"] == "port_protocol_shortcut_check")


def score(train, test, cfg, name, stage):
    frozen = frozen_result(name, stage)
    label = cfg["schema"]["label_column"]
    lookup_cfg = copy.deepcopy(cfg)
    lookup_cfg["schema"]["id_like_columns"] = ["_key"]
    lookup_cfg["schema"]["attack_category_column"] = None
    lookup = identity_columns.check_predictive_power(train[["_key", label]], test[["_key", label]], lookup_cfg)
    d = lookup["details"]
    return {"port_column": frozen["details"]["port_column"], "protocol_column": frozen["details"]["protocol_column"],
            "frozen_status": frozen["status"], "frozen_auc": frozen["details"]["standalone_auc"],
            "lookup_status": lookup["status"],
            "lookup": {k: d[k]["_key"] for k in ("standalone_auc", "seen_only_auc", "seen_coverage") if "_key" in d.get(k, {})}}


def main():
    name = sys.argv[1]
    run = RUNS[name]
    cfg = load_config(str(CONFIGS / f"{name}.yaml"))
    chunk_size = cfg["dataset"]["chunk_size"] or 200_000
    label = cfg["schema"]["label_column"]
    if run["split"] == "random":
        files = run["files"]
        all_columns = list(dict.fromkeys(c for p in files for c in header(p)))
        combined, port, proto = reduce(files, cfg, chunk_size, all_columns)
        print(f"  {len(combined):,} rows", flush=True)
        train, test = train_test_split(combined, test_size=1.0 - cfg["dataset"]["split_ratio"],
                                       random_state=cfg["random_seed"], stratify=combined[label])
        del combined
        train, test = train.reset_index(drop=True), test.reset_index(drop=True)
    else:
        all_columns = list(dict.fromkeys(c for p in run["train"] + run["test"] for c in header(p)))
        train, port, proto = reduce(run["train"], cfg, chunk_size, all_columns)
        test, _, _ = reduce(run["test"], cfg, chunk_size, all_columns)
    result = {"before_dedup": score(train, test, cfg, name, "before")}
    print("  before dedup:", result["before_dedup"], flush=True)
    train, test, stats = dedup(train, test)
    result["dedup_stats"] = stats
    result["dedup_matches_table6"] = all(stats[k] == v for k, v in run["table6"].items())
    print("  dedup:", stats, "| matches Table 6:", result["dedup_matches_table6"], flush=True)
    result["after_dedup"] = score(train, test, cfg, name, "after")
    print("  after dedup:", result["after_dedup"], flush=True)
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    results[name] = result
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print("DONE")


if __name__ == "__main__":
    main()
