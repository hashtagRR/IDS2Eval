#!/usr/bin/env python3
"""Prepare CTU-13 for the pre-registered external audit.

Reads the bidirectional NetFlow file (*.binetflow) of each of the 13
scenarios from the dataset owners' release (Garcia et al., 2014; the owners
advise against the unidirectional NetFlows), and writes one gzipped CSV.

Label rule, fixed before the data was seen (results/preregistration/ctu13/
analysis_plan.md):
  botnet       the owners' label contains "Botnet" (traffic from or to an
               infected host, command-and-control included)
  normal       otherwise, the label contains "Normal"
  (excluded)   everything else: the owners' "Background" traffic, whose
               ground truth is unknown

Added columns: label (botnet / normal), family (the scenario's botnet family
for botnet rows, "normal" for normal rows), scenario (1-13), original_label
(the owners' label, kept for reference and excluded from the features).

Reads in chunks so a scenario never has to fit in memory at once. Writes a
JSON manifest beside the output with each input file's SHA-256, the rows per
scenario and label, and the background rows excluded.

Usage: python3 validation/ctu13_prepare.py DATA_DIR OUT_CSV_GZ
  DATA_DIR holds one folder per scenario, named 1 to 13, each with its
  .binetflow file.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

# Botnet family of each scenario, from the owners' scenario table.
FAMILY = {1: "Neris", 2: "Neris", 3: "Rbot", 4: "Rbot", 5: "Virut", 6: "Menti", 7: "Sogou",
          8: "Murlo", 9: "Neris", 10: "Rbot", 11: "Rbot", 12: "NSIS.ay", 13: "Virut"}
CHUNK_ROWS = 500_000
# Ports can be hexadecimal strings in this release; read them as text.
TEXT_COLUMNS = {"Sport": str, "Dport": str, "sTos": str, "dTos": str, "State": str, "Dir": str}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def relabel(original: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=original.index, dtype="object")
    text = original.astype(str)
    out[text.str.contains("Normal", regex=False)] = "normal"
    out[text.str.contains("Botnet", regex=False)] = "botnet"  # takes precedence
    return out


def main() -> None:
    data_dir, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"label_rule": "botnet if the label contains 'Botnet', else normal if it contains "
                              "'Normal', else excluded (background)", "scenarios": {}}
    header_written = False
    with gzip.open(out_path, "wt", newline="") as out:
        for scenario in range(1, 14):
            files = sorted((data_dir / str(scenario)).glob("*.binetflow"))
            if len(files) != 1:
                raise SystemExit(f"scenario {scenario}: expected one .binetflow file, found {len(files)}")
            path = files[0]
            counts = {"botnet": 0, "normal": 0, "background_excluded": 0}
            for chunk in pd.read_csv(path, chunksize=CHUNK_ROWS, dtype=TEXT_COLUMNS):
                label = relabel(chunk["Label"])
                kept = chunk[label.notna()].copy()
                counts["background_excluded"] += int(label.isna().sum())
                if kept.empty:
                    continue
                kept["original_label"] = kept.pop("Label")
                kept["label"] = label[label.notna()].to_numpy()
                kept["family"] = kept["label"].where(kept["label"] == "normal", FAMILY[scenario])
                kept["scenario"] = scenario
                counts["botnet"] += int((kept["label"] == "botnet").sum())
                counts["normal"] += int((kept["label"] == "normal").sum())
                kept.to_csv(out, index=False, header=not header_written)
                header_written = True
            manifest["scenarios"][str(scenario)] = {
                "file": path.name, "sha256": sha256(path), "family": FAMILY[scenario], **counts,
            }
            print(scenario, path.name, counts, flush=True)
    manifest["output_sha256_compressed"] = sha256(out_path)
    out_path.with_suffix("").with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
