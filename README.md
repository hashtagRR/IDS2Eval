# IDS2Eval

A config-driven data-quality-audit and benchmarking toolkit for network intrusion detection (NIDS) datasets.

Most published NIDS results are evaluated on benchmark datasets (UNSW-NB15, CIC-IDS2018, and others) whose quality is largely taken on faith. IDS2Eval operationalizes a systematic audit methodology — feature-importance-driven leakage screening, a nearest-neighbor class-homogeneity test, a resplit falsification test, identity-column and low-cardinality checks, and more — as reusable, config-driven software, rather than a one-off analysis notebook per dataset.

Unlike general-purpose AutoML tools (PyCaret, AutoGluon, TPOT), IDS2Eval's focus is IDS-specific, already-validated data-quality checks rather than breadth of ML algorithms.

## Status

Implemented and tested:
- Dataset loading (raw files or pre-split train/test), with both a plain random split and a session/time-grouped split (`ids2eval/dataset.py`)
- Chunked reading for large files (`dataset.chunk_size`) with an optional reservoir-sampled row cap (`dataset.max_rows`) so a dataset larger than RAM can still be used — see `configs/schema.yaml` for the tradeoff each one actually controls (`ids2eval/chunked_io.py`)
- Feature-space exact-duplicate removal, within and across splits
- All 11 audit checks — 8 v1 + 3 v2 (`ids2eval/audit/`) — see below
- Config schema + validating loader (`ids2eval/config.py`, `configs/schema.yaml`)
- Preprocessing: scaling (standard/minmax/robust) and class balancing (SMOTE/SMOTEENN/ENN/random undersampling), fit on train only (`ids2eval/preprocessing.py`)
- Classifier benchmarking across the 14 supported classifiers, with optional GridSearchCV tuning and calibration (`ids2eval/benchmark.py`, `ids2eval/classifiers.py`)
- A CLI entrypoint wiring all of the above together (`python -m ids2eval`)
- A 71-test pytest suite (`tests/`) and pip-installable packaging (`pyproject.toml`, `ids2eval` console script)

Validated against real data, not just synthetic fixtures:
- UNSW-NB15 (full dataset, both files) — audit checks and all 5 tested classifiers ran cleanly end to end
- CIC-IDS2018 (official 10-file, 16.2M-row distribution) — `chunk_size`/`max_rows` kept peak memory at 3.0GB on a 7.8GB-RAM machine; `identity_column_flag` independently reproduced the published `Dst Port` leakage finding

Not yet implemented:
- CI/lint automation
- A curated `known_issue_lookup` table beyond its current two seed entries

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
| `synthetic_realism_check` *(v2, off by default)* | Domain-classifier AUC distinguishing this dataset from `audit.reference_dataset`, plus per-feature KS-divergence ranking |
| `cross_dataset_drift_check` *(v2, off by default)* | Train-here/test-on-`reference_dataset` accuracy drop in a unified feature space |
| `known_issue_lookup` *(v2, off by default)* | Curated per-dataset documented problems, matched on `dataset.name` — no reference dataset needed |

The two reference-data checks require `audit.reference_dataset` (a second dataset in the same schema — a real-traffic sample for realism, or an independent dataset for drift). `known_issue_lookup` needs neither, just a `dataset.name` match against the curated table in `ids2eval/audit/known_issues.py`.

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

```bash
python -m ids2eval --config my_config.yaml
```

Writes `audit_report.json`, the preprocessed `train`/`test` files (parquet by default), and `benchmark_results.csv` to `output.dir`. Use `--skip-audit` or `--skip-benchmark` to run only part of the pipeline.

Or drive it programmatically:

```python
from ids2eval.config import load_config
from ids2eval import dataset
from ids2eval.audit import run_audit
from ids2eval.benchmark import run_benchmark

cfg = load_config("my_config.yaml")
train_df, test_df = dataset.load_split(cfg)
findings = run_audit(train_df, test_df, cfg)  # call before dataset.dedup()
train_df, test_df, _ = dataset.dedup(train_df, test_df, cfg)
results_df = run_benchmark(train_df, test_df, cfg)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
