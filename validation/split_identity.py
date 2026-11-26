#!/usr/bin/env python3
"""How much the grouped split changes from seed to seed, and what it does to each class.

repeated_seed_falsification_check reshuffles the grouped split with each seed,
through scikit-learn's StratifiedGroupKFold(shuffle=True). That shuffle only
reorders groups that tie on the standard deviation of their class counts, so
a key with few groups of distinct sizes can give the same split on every seed;
the seed-to-seed spread of the check then comes from the model seed alone.

For each configuration this script rebuilds the grouped split for seeds 0 to 9
(no model is fitted) and reports the number of distinct test sets, and the
training and test rows of each class and, if configured, each attack category.

Run from the directory that holds data/.

Usage: python3 validation/split_identity.py OUT_JSON CONFIG[:KEY] [...]
  CONFIG is a config name in results/configs or a path to a config file; KEY is a
  grouping key from grouping_keys.KEYS (default: the config's own group_columns).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grouping_keys import KEYS, config_path, load_analysis_config

from ids2eval.data import dataset

N_SEEDS = 10


def main() -> None:
    out = Path(sys.argv[1])
    results = json.loads(out.read_text()) if out.exists() else {}
    for arg in sys.argv[2:]:
        name, _, key = arg.partition(":")
        path = config_path(name)
        entry_name = f"{path.stem}:{key}" if key else path.stem
        if entry_name in results:
            continue
        cfg = load_analysis_config(path)
        if key:
            cfg["dataset"]["group_columns"] = KEYS[path.stem][key]
        label_col = cfg["schema"]["label_column"]
        category_col = cfg["schema"].get("attack_category_column")
        combined = dataset.load_raw_combined(cfg["dataset"], seed=cfg["random_seed"])
        # _grouped_split resets the index, so carry each row's identity in a column
        combined["__row_id"] = range(len(combined))
        # With pandas 3, astype(str) keeps missing values as NaN, which breaks the group
        # key; fill them with "nan", as astype(str) did in the environments the audits ran in.
        for col in cfg["dataset"]["group_columns"]:
            if col in combined and combined[col].isna().any():
                combined[col] = combined[col].astype(object).where(combined[col].notna(), "nan")
        hashes, support = [], {}
        for seed in range(N_SEEDS):
            train, test = dataset._grouped_split(combined, label_col, cfg["dataset"], seed=seed)
            ids = sorted(test["__row_id"].tolist())
            hashes.append(hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest()[:16])
            for col in {label_col, category_col} - {None}:
                tr, te = train[col].value_counts(), test[col].value_counts()
                for c in sorted(set(tr.index) | set(te.index), key=str):
                    support.setdefault(col, {}).setdefault(str(c), []).append([int(tr.get(c, 0)), int(te.get(c, 0))])
        results[entry_name] = {
            "group_columns": cfg["dataset"]["group_columns"], "distinct_test_sets": len(set(hashes)),
            "test_set_hashes": hashes, "train_test_rows_by_seed": support,
        }
        out.write_text(json.dumps(results, indent=2) + "\n")
        print(entry_name, "distinct test sets:", len(set(hashes)), flush=True)


if __name__ == "__main__":
    main()
