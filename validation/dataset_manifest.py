#!/usr/bin/env python3
"""Provenance manifest of the dataset files behind the paper.

For every file an audit read, records where it came from, its name, its
size as stored here, and the SHA-256 of its uncompressed content (the
local copies were gzipped on download, so a checksum of the .gz would not
match what a reader downloads). A .sha256 file written at download time is
used when present; otherwise the content is hashed by streaming it.

Writes results/dataset_manifest.json and results/dataset_manifest.md.

Usage: venv/bin/python3 validation/dataset_manifest.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

DATA = Path("/home/tango/projects/IDS2Eval_data")
OUT = Path(__file__).resolve().parent.parent / "results"

CIC17 = ["Monday-WorkingHours", "Tuesday-WorkingHours", "Wednesday-workingHours",
         "Thursday-WorkingHours-Morning-WebAttacks", "Thursday-WorkingHours-Afternoon-Infilteration",
         "Friday-WorkingHours-Morning", "Friday-WorkingHours-Afternoon-PortScan", "Friday-WorkingHours-Afternoon-DDos"]
CIC18 = ["Wednesday-14-02-2018", "Thursday-15-02-2018", "Friday-16-02-2018", "Thuesday-20-02-2018",
         "Wednesday-21-02-2018", "Thursday-22-02-2018", "Friday-23-02-2018", "Wednesday-28-02-2018",
         "Thursday-01-03-2018", "Friday-02-03-2018"]

DATASETS = [
    {"dataset": "UNSW-NB15", "used_for": "Tables 5, 6; Section 4",
     "source": "GitHub mirror of the official training/testing partition: "
               "github.com/Nir-J/ML-Projects (UNSW-Network_Packet_Classification); "
               "official release at research.unsw.edu.au/projects/unsw-nb15-dataset; byte-identical to the copy "
               "Section 4 analyzed, whose file names are swapped (that copy's file named testing-set holds this "
               "training-set's bytes, Section 4.2)",
     "files": ["unsw-nb15/UNSW_NB15_training-set.csv.gz", "unsw-nb15/UNSW_NB15_testing-set.csv.gz"]},
    {"dataset": "NSL-KDD", "used_for": "Tables 5, 6",
     "source": "GitHub mirror github.com/defcom17/NSL_KDD (KDDTrain+.txt, KDDTest+.txt); the headerless files "
               "were given the standard KDD'99 column names at download, so the checksum covers the header line",
     "files": ["nsl-kdd/KDDTrain+.csv.gz", "nsl-kdd/KDDTest+.csv.gz"]},
    {"dataset": "CIC-IDS2017 (MachineLearningCSV)", "used_for": "Tables 5, 6",
     "source": "Hugging Face mirror huggingface.co/datasets/c01dsnap/CIC-IDS2017 of the official "
               "MachineLearningCSV.zip (www.unb.ca/cic/datasets/ids-2017.html)",
     "files": [f"cic-ids2017/{f}.pcap_ISCX.csv.gz" for f in CIC17]},
    {"dataset": "CIC-IDS2017 (GeneratedLabelledFlows)", "used_for": "Table 6a, Section 6.3",
     "source": "official GeneratedLabelledFlows.zip from UNB CIC (www.unb.ca/cic/datasets/ids-2017.html), "
               "extracted and gzipped",
     "files": [f"cic-ids2017/glf/{f}.pcap_ISCX.csv.gz" for f in CIC17]},
    {"dataset": "CSE-CIC-IDS2018", "used_for": "Tables 5, 6, 6a, 6b",
     "source": "official AWS S3 bucket cse-cic-ids2018, folder 'Processed Traffic Data for ML Algorithms'",
     "files": [f"cic-ids2018/{f}_TrafficForML_CICFlowMeter.csv.gz" for f in CIC18]},
    {"dataset": "CICDDoS2019", "used_for": "Tables 5, 6, 6a, Section 6.3",
     "source": "official CSV-01-12.zip (training day) and CSV-03-11.zip (testing day) from UNB CIC "
               "(www.unb.ca/cic/datasets/ddos-2019.html); each day's CSVs merged into one file "
               "(a stray LibreOffice lock file in CSV-03-11 excluded)",
     "files": ["cic-ddos2019/train-full.csv.gz", "cic-ddos2019/test-full.csv.gz"]},
    {"dataset": "ToN-IoT", "used_for": "Tables 5, 6, 6a, 6b",
     "source": "official Train_Test_Network.csv from UNSW (research.unsw.edu.au/projects/toniot-datasets)",
     "files": ["ton-iot-official/train_test_network.csv.gz"]},
    {"dataset": "BoT-IoT", "used_for": "Tables 5, 6, 6a, 6b",
     "source": "OpenML dataset 42072 'bot-iot-all-features', deposited by the dataset's authors "
               "(the official 5%-reduced, all-features release), stored as parquet; checksum of the parquet file",
     "files": ["bot-iot-official/bot-iot-all-features.parquet"]},
]


def sha256_of(path: Path) -> tuple[str, str]:
    stored = path.with_suffix("").with_suffix(".sha256") if path.suffix == ".gz" else Path(f"{path}.sha256")
    if stored.exists():
        return stored.read_text().split()[0], "recorded at download"
    h = hashlib.sha256()
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest(), "computed from the stored copy"


def main() -> None:
    manifest = []
    for entry in DATASETS:
        files = []
        for rel in entry["files"]:
            p = DATA / rel
            digest, how = sha256_of(p)
            files.append({"file": Path(rel).name.removesuffix(".gz"), "stored_as": rel,
                          "stored_bytes": p.stat().st_size, "sha256_uncompressed": digest, "checksum": how})
            print(entry["dataset"], rel, digest[:16], how, flush=True)
        manifest.append({**{k: v for k, v in entry.items() if k != "files"}, "files": files})
    (OUT / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2))
    lines = ["# Dataset provenance manifest", "",
             "The datasets are not redistributed here; download them from the sources below. The SHA-256 is of each "
             "file's uncompressed content, so a reader can check that a download matches the bytes these audits "
             "read. No official checksums exist for these releases to compare against.", ""]
    for e in manifest:
        lines += [f"## {e['dataset']}", "", f"Source: {e['source']}", "", f"Used for: {e['used_for']}", "",
                  "| File | SHA-256 (uncompressed) |", "|---|---|"]
        lines += [f"| `{f['file']}` | `{f['sha256_uncompressed']}` |" for f in e["files"]]
        lines.append("")
    (OUT / "dataset_manifest.md").write_text("\n".join(lines))
    print("DONE")


if __name__ == "__main__":
    main()
