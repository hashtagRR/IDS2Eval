# IDS2Eval

A config-driven data-quality-audit and benchmarking toolkit for network intrusion detection (NIDS) datasets.

Most published NIDS results are evaluated on benchmark datasets (UNSW-NB15, CIC-IDS2018, and others) whose quality is largely taken on faith. IDS2Eval operationalizes a systematic audit methodology — feature-importance-driven leakage screening, a nearest-neighbor class-homogeneity test, a resplit falsification test, identity-column and low-cardinality checks, and more — as reusable, config-driven software, rather than a one-off analysis notebook per dataset.

Unlike general-purpose AutoML tools (PyCaret, AutoGluon, TPOT), IDS2Eval's focus is IDS-specific, already-validated data-quality checks rather than breadth of ML algorithms.

## Status

Implemented and tested:
- Dataset loading (raw files or pre-split train/test), with both a plain random split and a session/time-grouped split (`ids2eval/dataset.py`)
- Feature-space exact-duplicate removal, within and across splits
- All 8 v1 audit checks (`ids2eval/audit/`) — see below
- Config schema + validating loader (`ids2eval/config.py`, `configs/schema.yaml`)

Not yet implemented:
- The preprocessing pipeline's scaling/sampling steps (schema exists, code doesn't yet)
- Classifier benchmarking across the 14 supported classifiers
- A CLI entrypoint tying the pieces together

## Audit checks

| Check | What it does |
|---|---|
| `dedup_check` | Reports exact feature-space duplicates within and across train/test |
| `leakage_screen` | Flags a single feature or pair carrying a large majority of a RandomForest's split importance, plus that feature's standalone AUC |
| `identity_column_flag` | Standalone predictive power of IP/port/MAC-like columns |
| `low_cardinality_warning` | Flags identity columns with few enough unique values to risk topology overfitting |
| `homogeneity_test` | Nearest-neighbor test-to-train vs. train-internal proximity, per class, to distinguish inherent class homogeneity from train/test leakage |
| `resplit_falsification` | Compares accuracy under a random split vs. a session-grouped split, where session-correlated leakage is structurally impossible |
| `class_distribution_report` | Per-class counts, shares, and imbalance ratio |
| `schema_fingerprint_check` | Matches known feature-extractor signatures (e.g. CICFlowMeter) and surfaces that extractor's documented bugs |

Three further checks (synthetic-vs-real realism, cross-dataset drift, a curated known-issue lookup table) are scoped for a later v2 — they need a second reference dataset or heavier compute and are off by default.

## Config

See `configs/schema.yaml` for the full, commented schema. A minimal config needs:

```yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

## Usage

```python
from ids2eval.config import load_config
from ids2eval import dataset
from ids2eval.audit import run_audit

cfg = load_config("my_config.yaml")
train_df, test_df = dataset.load_split(cfg)
findings = run_audit(train_df, test_df, cfg)  # call before dataset.dedup()
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
