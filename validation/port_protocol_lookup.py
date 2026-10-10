#!/usr/bin/env python3
"""Re-scores port_protocol_shortcut_check with the training-only lookup.

The frozen check integer-codes the (port, protocol) pair with codes fit on
training and gives every pair unseen in training the code -1, which a tree
cannot separate from code 0, the flaw identity_column_flag's redesign
removed. This scores the same pair, on the same audited split, with
identity_column_flag's lookup (training-only class frequencies per value,
smoothed toward the prior; unseen values get the prior), and reports the
share of test rows whose pair occurs in training, so the size of the
difference and its cause are both visible.

Usage: venv/bin/python3 validation/port_protocol_lookup.py NAME:RAW_FILE [...]
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ids2eval.audit import identity_columns, port_protocol_shortcut
from ids2eval.config import load_config
from ids2eval.data import dataset

CONFIG_DIR = Path("/home/tango/projects/IDS2Eval_data/configs")
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "port_protocol_lookup.json"


def score(train, test, cfg):
    frozen = port_protocol_shortcut.check(train, test, cfg)
    port, proto = frozen["details"].get("port_column"), frozen["details"].get("protocol_column")
    if port is None:
        port = port_protocol_shortcut._find_column(
            [c for c in cfg["schema"]["id_like_columns"] if c in train.columns], "port")
        proto = port_protocol_shortcut._find_column(list(train.columns), "proto")
    key = "_port_proto"
    tr, te = train.copy(), test.copy()
    for df in (tr, te):
        df[key] = df[port].astype(str) + "|" + df[proto].astype(str)
    lookup_cfg = copy.deepcopy(cfg)
    lookup_cfg["schema"]["id_like_columns"] = [key]
    lookup = identity_columns.check_predictive_power(tr, te, lookup_cfg)
    d = lookup["details"]
    col = {k: d[k][key] for k in ("standalone_auc", "seen_only_auc", "seen_coverage") if key in d.get(k, {})}
    return {"port_column": port, "protocol_column": proto, "frozen_status": frozen["status"],
            "frozen_auc": frozen["details"].get("standalone_auc"),
            "frozen_summary": frozen["summary"], "lookup_status": lookup["status"],
            "lookup_summary": lookup["summary"], "lookup_details": col}


def main():
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for arg in sys.argv[1:]:
        name, raw = arg.split(":", 1)
        cfg = load_config(str(CONFIG_DIR / f"{name}.yaml"))
        cfg["dataset"]["raw_files"] = [raw]
        label_col = cfg["schema"]["label_column"]
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        train, test = dataset._random_split(combined, label_col, cfg["dataset"], seed=cfg["random_seed"])
        out = {"before_dedup": score(train, test, cfg)}
        train_d, test_d, _ = dataset.dedup(train.copy(), test.copy(), cfg)
        out["after_dedup"] = score(train_d, test_d, cfg)
        results[name] = out
        OUT.write_text(json.dumps(results, indent=2, default=str))
        for stage, r in out.items():
            print(name, stage, "| frozen:", r["frozen_status"], r["frozen_summary"][:80], "| lookup:",
                  r["lookup_status"], r["lookup_summary"][:160], flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
