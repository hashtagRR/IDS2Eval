#!/usr/bin/env python3
"""Why do one-shot falsification checks flag clean synthetic data?

Regenerates the clean flow-like datasets of heldout_validation.part2 (same
generator, seeds and split) and records, per dataset, the numbers behind
resplit_falsification's and result_robustness_check's verdicts (accuracies,
gap, sampling margin, test sizes, per-condition accuracies) alongside
repeated_seed_falsification_check's interval, so the false flags can be
read individually rather than only counted.

Usage: venv/bin/python3 validation/clean_flag_diagnosis.py [SEED_START]
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
from heldout_validation import CLEAN_APPLICABLE, GROUP, clean_dataset  # noqa: E402

from ids2eval.audit import repeated_seed_falsification, resplit, result_robustness  # noqa: E402
from ids2eval.config import DEFAULTS  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "clean_flag_diagnosis.json"


def main() -> None:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for bal, m in {"balanced": 0.5, "imbalanced_10pct": 0.1, "imbalanced_2pct": 0.02}.items():
            for seed in range(start, start + 10):
                df = clean_dataset(np.random.default_rng(seed), m)
                path = Path(tmp) / f"clean_{bal}_{seed}.csv"
                df.to_csv(path, index=False)
                cfg = copy.deepcopy(DEFAULTS)
                cfg["dataset"].update({"name": f"clean-{bal}-{seed}", "raw_files": [str(path)],
                                       "group_columns": list(GROUP)})
                cfg["schema"].update({"label_column": "label", "drop_columns": ["ts"],
                                      "id_like_columns": ["src_ip", "dst_ip", "src_port", "dst_port"],
                                      "flow_id_columns": list(GROUP), "timestamp_column": "ts"})
                for name in CLEAN_APPLICABLE:
                    cfg["audit"][name] = True
                cfg["audit"]["repeated_seed_count"] = 5
                rs = resplit.check(cfg)
                rb = result_robustness.check(cfg)
                rp = repeated_seed_falsification.check(cfg)
                row = {"balance": bal, "seed": seed, "majority_rate": float(1 - m),
                       "resplit": {"status": rs["status"], **{k: rs["details"].get(k) for k in (
                           "random_accuracy", "grouped_accuracy", "drop", "sampling_margin",
                           "random_test_rows", "grouped_test_rows")}},
                       "robustness": {"status": rb["status"], "summary": rb["summary"],
                                      "sampling_margin": rb["details"].get("sampling_margin"),
                                      "spread": rb["details"].get("spread"),
                                      "accuracy_by_condition": rb["details"].get("accuracy_by_condition")},
                       "repeated_seed": {"status": rp["status"], "summary": rp["summary"]}}
                rows.append(row)
                print(bal, seed, rs["status"], rb["status"], rp["status"], "|", rs["summary"][:110], "|",
                      rb["summary"][:140], flush=True)
    OUT.write_text(json.dumps(rows, indent=2, default=str))
    print("DONE")


if __name__ == "__main__":
    main()
