#!/usr/bin/env python3
"""Relabel the corrected CIC-IDS2017 release's "Attempted" flows as BENIGN.

The release's maintainers (KU Leuven, intrusion-detection.distrinet-research.be/
CNS2022/Dataset_Download.html) state that "Attempted" flows must never be a
separate label for a machine-learning model, and recommend relabelling them as
benign when in doubt, identifying them by an "Attempted Category" value other
than -1. This script applies that recommendation to the five day files and
writes them, gzipped, under the same names; every other column is unchanged.
A JSON manifest beside the output records each input's SHA-256 and the rows
relabelled per original label.

Usage: python3 validation/cic17_attempted_benign.py IN_DIR OUT_DIR
  IN_DIR holds monday.csv.gz ... friday.csv.gz as distributed in the bucket.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
CHUNK_ROWS = 400_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    in_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"rule": 'Label := "BENIGN" where "Attempted Category" != -1', "days": {}}
    for day in DAYS:
        src, dst = in_dir / f"{day}.csv.gz", out_dir / f"{day}.csv.gz"
        relabelled: dict[str, int] = {}
        rows = 0
        with gzip.open(dst, "wt", newline="") as out:
            for i, chunk in enumerate(pd.read_csv(src, chunksize=CHUNK_ROWS, low_memory=False)):
                attempted = pd.to_numeric(chunk["Attempted Category"], errors="coerce").fillna(-1) != -1
                for label, count in chunk.loc[attempted, "Label"].value_counts().items():
                    relabelled[label] = relabelled.get(label, 0) + int(count)
                chunk.loc[attempted, "Label"] = "BENIGN"
                rows += len(chunk)
                chunk.to_csv(out, index=False, header=(i == 0))
        manifest["days"][day] = {"input_sha256_compressed": sha256(src), "rows": rows,
                                 "relabelled_to_benign": relabelled}
        print(day, rows, sum(relabelled.values()), "relabelled", flush=True)
    (out_dir / "attempted_benign_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
