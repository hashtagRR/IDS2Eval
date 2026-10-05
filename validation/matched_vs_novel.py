#!/usr/bin/env python3
"""Does cross-boundary feature-vector reuse help the classifier?

For each cached dataset, fits the same reference model the falsification
checks use (RandomForest, 100 trees, 200,000-row training cap) on the
audited random split, then compares test accuracy on "matched" rows (whose
exact feature vector, compared on dedup_check's columns, also appears in
training) with "novel" rows. Also reports how often a matched row's label
agrees with the majority training label for that same vector.

Usage: venv/bin/python3 validation/matched_vs_novel.py
"""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ids2eval.config import load_config
from ids2eval.data import features

DATA = Path("/home/tango/projects/IDS2Eval_data")
DATASETS = ["unsw-nb15", "nsl-kdd", "cic-ids2017", "cic-ddos2019", "ton-iot-official", "cic-ids2018"]
MAX_FIT_ROWS = 200_000
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "matched_vs_novel.json"


def feature_hash(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return pd.util.hash_pandas_object(df[cols].astype(str), index=False)


def main() -> None:
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for name in DATASETS:
        if name in results:
            continue
        cfg = load_config(str(DATA / "configs" / f"{name}.yaml"))
        label = cfg["schema"]["label_column"]
        cache = DATA / "output" / name / ".cache"
        train, test = pd.read_parquet(cache / "train.parquet"), pd.read_parquet(cache / "test.parquet")
        schema = cfg["schema"]
        ignore = set(schema["drop_columns"]) | {label}
        if schema["attack_category_column"]:
            ignore.add(schema["attack_category_column"])
        dedup_cols = [c for c in train.columns if c not in ignore]

        h_train, h_test = feature_hash(train, dedup_cols), feature_hash(test, dedup_cols)
        matched = h_test.isin(set(h_train)).to_numpy()
        majority = pd.DataFrame({"h": h_train.to_numpy(), "y": train[label].astype(str).to_numpy()}) \
            .groupby("h")["y"].agg(lambda s: s.value_counts().idxmax())
        agree = (h_test[matched].map(majority).to_numpy() == test[label].astype(str).to_numpy()[matched])

        seed = cfg["random_seed"]
        cols = features.feature_columns(train, cfg)
        fit = train.sample(n=min(len(train), MAX_FIT_ROWS), random_state=seed)
        x_fit, x_test = features.encode_aligned(fit, test, cols)
        clf = RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1).fit(x_fit, fit[label])
        correct = (clf.predict(x_test) == test[label].to_numpy())

        results[name] = {
            "test_rows": len(test), "matched_rows": int(matched.sum()),
            "matched_share": float(matched.mean()),
            "accuracy_matched": float(correct[matched].mean()) if matched.any() else None,
            "accuracy_novel": float(correct[~matched].mean()) if (~matched).any() else None,
            "accuracy_all": float(correct.mean()),
            "matched_label_agreement": float(agree.mean()) if matched.any() else None,
        }
        print(name, results[name], flush=True)
        OUT.write_text(json.dumps(results, indent=2))
        del train, test, fit, x_fit, x_test, clf
        gc.collect()
    print("DONE")


if __name__ == "__main__":
    main()
