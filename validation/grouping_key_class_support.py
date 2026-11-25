#!/usr/bin/env python3
"""Class support under each grouping key: what the grouped split does to each class.

grouping_keys.py ran repeated_seed_falsification_check under the 5-tuple, a
coarse key and the source host. Those runs predate the class-support reporting
of resplit_falsification, so a material drop under a key could come from the
grouped split moving most of a class to one side. This script rebuilds the
same grouped splits (the same function and seeds 0 to 9 the check uses; no
model is fitted) and reports for every class its training and test rows per
seed, the share of its rows on the training side, and the seeds on which it
has no training or no test rows.

Run from the directory that holds data/.

Usage: python3 validation/grouping_key_class_support.py OUT_JSON DATASET[:KEY,KEY] [...]
  DATASET is a config name in results/configs; KEY limits the keys run
  (default: every key grouping_keys.py defines for the dataset).
"""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grouping_keys import KEYS, config_path, load_analysis_config

from ids2eval.data import dataset

N_SEEDS = 10


def support(combined, label_col, dataset_cfg, columns):
    cfg = json.loads(json.dumps(dataset_cfg))
    cfg["group_columns"] = columns
    per_seed, shares = [], {}
    for seed in range(N_SEEDS):
        train, test = dataset._grouped_split(combined, label_col, cfg, seed=seed)
        tr, te = train[label_col].value_counts(), test[label_col].value_counts()
        classes = sorted(set(tr.index) | set(te.index), key=str)
        rows = {str(c): [int(tr.get(c, 0)), int(te.get(c, 0))] for c in classes}
        per_seed.append({
            "seed": seed, "train_test_rows": rows,
            "missing_from_train": [c for c, (a, _) in rows.items() if a == 0],
            "missing_from_test": [c for c, (_, b) in rows.items() if b == 0],
        })
        for c, (a, b) in rows.items():
            shares.setdefault(c, []).append(a / (a + b))
        del train, test
        gc.collect()
    by_class = {c: {"train_share_min": min(v), "train_share_max": max(v),
                    "seeds_without_training_rows": sum(s == 0 for s in v),
                    "seeds_without_test_rows": sum(s == 1 for s in v),
                    "seeds_train_share_below_0.2": sum(s < 0.2 for s in v)}
                for c, v in shares.items()}
    return {"per_seed": per_seed, "by_class": by_class}


def main() -> None:
    out = Path(sys.argv[1])
    results = json.loads(out.read_text()) if out.exists() else {}
    for arg in sys.argv[2:]:
        name, _, only = arg.partition(":")
        path = config_path(name)
        cfg = load_analysis_config(path)
        keys = {k: v for k, v in KEYS[path.stem].items() if not only or k in only.split(",")}
        label_col = cfg["schema"]["label_column"]
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        for key_name, columns in keys.items():
            if key_name in results.get(path.stem, {}):
                continue
            entry = support(combined, label_col, cfg["dataset"], columns)
            results.setdefault(path.stem, {})[key_name] = entry
            out.write_text(json.dumps(results, indent=2) + "\n")
            worst = sorted(entry["by_class"].items(), key=lambda kv: kv[1]["train_share_min"])[:3]
            print(path.stem, key_name, [(c, round(v["train_share_min"], 3), v["seeds_without_training_rows"],
                                         v["seeds_without_test_rows"]) for c, v in worst], flush=True)
        del combined
        gc.collect()


if __name__ == "__main__":
    main()
