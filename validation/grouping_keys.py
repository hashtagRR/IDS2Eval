#!/usr/bin/env python3
"""Grouping-key granularity and the grouped resplit under coarser keys.

A grouped split only differs from a random one when the grouping key's groups
hold several rows. For each dataset with address or port columns this script
reports, per key, the group count, the share of single-row groups and the
group-size quantiles (over every row), and runs
repeated_seed_falsification_check (10 seeds, per-metric verdicts) under that
key:

  five_tuple  the key the audits used (source and destination address and
              port, protocol)
  coarse      source address, destination address, destination port,
              protocol (no ephemeral source port)
  host        source address alone

CSE-CIC-IDS2018's processed release has no address columns; its audit key is
a proxy (destination port, protocol, timestamp), and its coarser alternative
drops the timestamp.

Run from the directory that holds data/. Writes one entry per dataset and key
as soon as it finishes, so a rerun skips what is done.

Usage: python3 validation/grouping_keys.py OUT_JSON DATASET [DATASET ...]
  DATASET is a config name in results/configs (or a path to a config file).
"""
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ids2eval.audit import _groups, repeated_seed_falsification
from ids2eval.config import load_config
from ids2eval.data import dataset

CONFIGS = Path(__file__).resolve().parent.parent / "results" / "configs"

KEYS = {
    "ton-iot-official": {
        "five_tuple": ["src_ip", "src_port", "dst_ip", "dst_port", "proto"],
        "coarse": ["src_ip", "dst_ip", "dst_port", "proto"],
        "host": ["src_ip"],
    },
    "bot-iot-official": {
        "five_tuple": ["saddr", "sport", "daddr", "dport", "proto"],
        "coarse": ["saddr", "daddr", "dport", "proto"],
        "host": ["saddr"],
    },
    "cic-ids2017-glf": {
        "five_tuple": ["Source IP", "Source Port", "Destination IP", "Destination Port", "Protocol"],
        "coarse": ["Source IP", "Destination IP", "Destination Port", "Protocol"],
        "host": ["Source IP"],
    },
    "cic-ids2017-improved": {
        "five_tuple": ["Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol"],
        "coarse": ["Src IP", "Dst IP", "Dst Port", "Protocol"],
        "host": ["Src IP"],
    },
    "cic-ddos2019-fullscale-resplit": {
        "five_tuple": ["Source IP", "Source Port", "Destination IP", "Destination Port", "Protocol"],
        "coarse": ["Source IP", "Destination IP", "Destination Port", "Protocol"],
        "host": ["Source IP"],
    },
    "cic-ids2018-fullscale": {
        "proxy": ["Dst Port", "Protocol", "Timestamp"],
        "proxy_without_time": ["Dst Port", "Protocol"],
    },
}


def config_path(name: str) -> Path:
    path = Path(name)
    return path if path.suffix in {".yaml", ".yml"} else CONFIGS / f"{name}.yaml"


def main() -> None:
    out = Path(sys.argv[1])
    results = json.loads(out.read_text()) if out.exists() else {}
    for name in sys.argv[2:]:
        path = config_path(name)
        cfg = load_config(str(path))
        keys = KEYS[path.stem]
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        for key_name, columns in keys.items():
            if key_name in results.get(path.stem, {}):
                continue
            run_cfg = json.loads(json.dumps(cfg))
            run_cfg["dataset"]["group_columns"] = columns
            run_cfg["audit"]["repeated_seed_count"] = 10
            started = time.time()
            entry = {"group_stats": _groups.group_stats(combined, columns)}
            try:
                entry["repeated_seed"] = repeated_seed_falsification.check(run_cfg, combined=combined)
            except (ValueError, RuntimeError) as error:  # a key that cannot be split stratified
                entry["repeated_seed"] = {"status": "not_applicable", "summary": str(error)}
            entry["seconds"] = round(time.time() - started)
            results.setdefault(path.stem, {})[key_name] = entry
            out.write_text(json.dumps(results, indent=2, default=str) + "\n")
            print(path.stem, key_name, _groups.describe(entry["group_stats"]), "|",
                  entry["repeated_seed"]["summary"][:260], flush=True)
            gc.collect()
        del combined
        gc.collect()


if __name__ == "__main__":
    main()
