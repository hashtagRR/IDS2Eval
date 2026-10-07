#!/usr/bin/env python3
"""How many CICDDoS2019 grouped-split test rows carry an IP never seen in training?

Bounds the effect of the unseen-category encoding fix on the full-release
CICDDoS2019 resplit result without re-running it. The grouped split keeps
every 5-tuple group on one side, with about 20% of groups in test. A test
row's Source IP (or Destination IP) value is absent from training only if
every 5-tuple group containing that IP landed in test, which for an IP in g
groups happens with probability about 0.2**g. Streaming both official day
files (only the 5-tuple columns), this counts rows and distinct groups per
IP and reports the expected share of test rows whose value is unseen,
per column, and their sum as an upper bound on rows with either unseen.

Usage: venv/bin/python3 validation/ddos_unseen_ip.py FILE [FILE ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

GROUP = ["Source IP", "Source Port", "Destination IP", "Destination Port", "Protocol"]
IP_COLS = ["Source IP", "Destination IP"]
Q = 0.2  # share of groups in test (split_ratio 0.8)
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "ddos_unseen_ip.json"


def main():
    pairs = {c: [] for c in IP_COLS}
    rows = {c: [] for c in IP_COLS}
    n = 0
    for path in sys.argv[1:]:
        for chunk in pd.read_csv(path, usecols=lambda c: c.strip() in GROUP, chunksize=2_000_000,
                                 dtype=str, low_memory=False):
            chunk.columns = [c.strip() for c in chunk.columns]
            n += len(chunk)
            g = pd.util.hash_pandas_object(chunk[GROUP], index=False).to_numpy()
            for c in IP_COLS:
                ip = pd.util.hash_pandas_object(chunk[c], index=False).to_numpy()
                pair = np.unique(np.stack([ip, g], axis=1), axis=0)
                pairs[c].append(pair)
                vals, cnt = np.unique(ip, return_counts=True)
                rows[c].append(np.stack([vals, cnt.astype(np.uint64)], axis=1))
            print(f"{path.split('/')[-1]}: {n:,} rows", flush=True)
    result = {"rows": n, "q": Q}
    for c in IP_COLS:
        p = np.unique(np.concatenate(pairs[c]), axis=0)
        ips_g, groups_per_ip = np.unique(p[:, 0], return_counts=True)
        r = np.concatenate(rows[c])
        order = np.argsort(r[:, 0], kind="stable")
        r = r[order]
        ips_r, start = np.unique(r[:, 0], return_index=True)
        rows_per_ip = np.add.reduceat(r[:, 1], start)
        if not np.array_equal(ips_g, ips_r):
            raise RuntimeError(f"{c}: IP sets of the group and row counts differ")
        expected_unseen_test_rows = float((rows_per_ip * Q ** groups_per_ip.astype(float)).sum())
        share = expected_unseen_test_rows / (Q * n)
        result[c] = {"distinct_ips": len(ips_g), "ips_in_one_group": int((groups_per_ip == 1).sum()),
                     "rows_of_ips_in_one_group": int(rows_per_ip[groups_per_ip == 1].sum()),
                     "expected_unseen_share_of_test_rows": share}
        print(c, result[c], flush=True)
    result["upper_bound_either_unseen"] = sum(result[c]["expected_unseen_share_of_test_rows"] for c in IP_COLS)
    OUT.write_text(json.dumps(result, indent=2))
    print("upper bound, share of test rows with an unseen IP:", result["upper_bound_either_unseen"])
    print("DONE")


if __name__ == "__main__":
    main()
