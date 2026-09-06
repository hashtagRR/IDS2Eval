# IDS2Eval

A config-driven data-quality-audit and benchmarking toolkit for network intrusion detection (NIDS) datasets.

Most published NIDS results are evaluated on benchmark datasets (UNSW-NB15, CIC-IDS2018, and others) whose quality is largely taken on faith. IDS2Eval operationalizes a systematic audit methodology — feature-importance-driven leakage screening, a nearest-neighbor class-homogeneity test, a resplit falsification test, identity-column and low-cardinality checks, and more — as reusable, config-driven software, rather than a one-off analysis notebook per dataset.

Unlike general-purpose AutoML tools (PyCaret, AutoGluon, TPOT), IDS2Eval's focus is IDS-specific, already-validated data-quality checks rather than breadth of ML algorithms — feature engineering (imputation strategies, feature selection, dimensionality reduction) is deliberately out of scope for the same reason.

## Status

Implemented and tested:
- Dataset loading (raw files or pre-split train/test), with both a plain random split and a session/time-grouped split (`ids2eval/dataset.py`)
- Chunked reading for large files (`dataset.chunk_size`) with an optional reservoir-sampled row cap (`dataset.max_rows`) so a dataset larger than RAM can still be used — see `configs/schema.yaml` for the tradeoff each one actually controls (`ids2eval/chunked_io.py`)
- Hard-fail validation on structurally broken input (duplicate column names, a train/test schema sharing no feature columns) before anything downstream runs (`dataset.validate_loaded`)
- Feature-space exact-duplicate removal, within and across splits
- All 12 audit checks — 9 v1 + 3 v2 (`ids2eval/audit/`) — see below. When `preprocessing.dedup` is on, the full suite runs twice: once before dedup, once after, so a claim like "12% duplicate leakage before, 0% after" is backed by two real runs, not assumed
- Config schema + validating loader (`ids2eval/config.py`, `configs/schema.yaml`)
- `label_grouping.attack_type_mapping` — partial merge of raw attack categories into coarser ones (e.g. `{"DoS Hulk": "DoS"}`), applied before both audit and benchmarking
- Preprocessing: scaling (standard/minmax/robust) and class balancing (SMOTE/SMOTEENN/ENN/random undersampling, one strategy or a list to compare several), run **inside** each classifier's own fit — see the correctness note below, this isn't just an implementation detail
- Classifier benchmarking across the 14 supported classifiers, with optional GridSearchCV tuning and calibration, reporting per-classifier training/inference time, a confusion matrix, per-class precision/recall/F1, feature importance where supported, and the winning hyperparameters (`ids2eval/benchmark.py`, `ids2eval/classifiers.py`)
- A CLI entrypoint wiring all of the above together (`python -m ids2eval`)
- Caches the load+split+label-grouping result under `output.dir/.cache/` (`ids2eval/cache.py`) — the expensive step for large datasets, per measurement on real CIC-IDS2018 data. A fingerprint of the input files and the config fields that affect this step auto-invalidates the cache
- Every invocation gets its own `output.dir/runs/<timestamp>/` directory (config snapshot, environment info incl. `ids2eval`'s own version/git commit, both audit reports, benchmark results, a real content-hash `dataset_fingerprint.json`, and a `run_status.json` recording completion or which stage failed) so nothing is silently overwritten; `output.keep_runs` prunes old ones automatically without ever touching the cache
- `random_seed` (default 0) is the single source for every split/sampling/classifier-init seed in the data and benchmark pipeline, replacing what used to be 6 scattered hardcoded constants — a run is fully reproducible from `resolved_config.json` alone, verified directly: identical seed reproduces identical accuracy/F1/AUC to the last digit on real data, a different seed changes the result, and changing it correctly invalidates the load-cache
- A 121-test pytest suite (`tests/`) and pip-installable packaging (`pyproject.toml`, `ids2eval` console script)
- CI on every push/PR (tests across Python 3.10/3.11/3.12, ruff lint including security rules) plus CodeQL static analysis and scheduled Dependabot dependency updates (`.github/`)

**Correctness note — scaling/sampling and cross-validation.** Both run inside the same `imblearn` pipeline as the classifier, not once up front, so `classifiers.tuning`'s internal CV folds and `classifiers.calibration`'s internal folds each redo scaling/sampling independently. Fitting a scaler or a sampler like SMOTE once on the whole training set and only then handing the result to `GridSearchCV`/`CalibratedClassifierCV` lets their internal folds see data transformed using information from other, supposedly-held-out folds — SMOTE's synthetic points are the sharpest version of this, since a fold's synthetic rows can be interpolated from real neighbors that landed in a different fold. A single plain fit with no tuning or calibration was never affected by this (no internal CV, nowhere for it to happen), but now shares the same code path rather than a separate one.

Validated against real data, not just synthetic fixtures:
- UNSW-NB15 (full dataset, both files) — audit checks and 5 classifiers, including `tuning: true` with a multi-strategy sampling comparison (`none`/`smote`), ran cleanly end to end. The post-dedup audit showed class balance shift from 2:1 to roughly 1:1 — duplicated rows were disproportionately one class, a real finding surfaced by the before/after audit. Feature importance independently reproduced two published findings: UNSW-NB15's `sttl` TTL-topology bias here, and CIC-IDS2018's `Dst Port` leakage below
- CIC-IDS2018 (official 10-file, 16.2M-row distribution) — `chunk_size`/`max_rows` kept peak memory at 3.0GB on a 7.8GB-RAM machine; `identity_column_flag` independently reproduced the published `Dst Port` leakage finding

Not yet implemented:
- A curated `known_issue_lookup` table beyond its current two seed entries
- Automatic comparison across *scaling* strategies (sampling already supports a list; scaling is still single-valued)
- `random_seed` doesn't reach audit checks' own internal sampling (deliberate — diagnostic, not part of the reported experimental result) or a few nested sub-estimators (AdaBoost's fixed depth-1 stump, Stacking/Voting's base learners)

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
| `data_integrity_check` | Missing label values, missing/constant feature columns, ±inf values — the complement of `leakage_screen`: features with too *little* signal, or garbage values, rather than too much |
| `synthetic_realism_check` *(v2, off by default)* | Domain-classifier AUC distinguishing this dataset from `audit.reference_dataset`, plus per-feature KS-divergence ranking |
| `cross_dataset_drift_check` *(v2, off by default)* | Train-here/test-on-`reference_dataset` accuracy drop in a unified feature space |
| `known_issue_lookup` *(v2, off by default)* | Curated per-dataset documented problems, matched on `dataset.name` — no reference dataset needed |

The two reference-data checks require `audit.reference_dataset` (a second dataset in the same schema — a real-traffic sample for realism, or an independent dataset for drift). `known_issue_lookup` needs neither, just a `dataset.name` match against the curated table in `ids2eval/audit/known_issues.py`.

Structural problems severe enough to make the dataset unusable — duplicate column names, a train/test schema sharing no feature columns — aren't audit findings; they raise immediately via `dataset.validate_loaded()`, before caching or auditing even start.

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

Writes to a fresh `output.dir/runs/<timestamp>/` directory each run: `audit_report_before.json` (and `audit_report_after.json` if `preprocessing.dedup` is on), the preprocessed `train`/`test` files (parquet by default), `benchmark_results.csv`, `benchmark_details.json` (confusion matrices, per-class reports, feature importance, best hyperparameters), `environment.json`, `resolved_config.json`, `dataset_fingerprint.json` (row/feature counts, class distributions, content hashes — proof two runs used identical data), and `run_status.json` (`completed`, or `failed` with which stage and why). `output.keep_runs` (default 10) prunes older run directories automatically; `output.dir/.cache/` is untouched by that pruning. Use `--skip-audit` or `--skip-benchmark` to run only part of the pipeline.

Or drive it programmatically:

```python
from ids2eval.config import load_config
from ids2eval import dataset
from ids2eval.audit import run_audit
from ids2eval.benchmark import run_benchmark

cfg = load_config("my_config.yaml")
train_df, test_df = dataset.load_split(cfg)
dataset.validate_loaded(train_df, test_df, cfg)
findings = run_audit(train_df, test_df, cfg)  # call before dataset.dedup()
train_df, test_df, _ = dataset.dedup(train_df, test_df, cfg)
results_df, extras = run_benchmark(train_df, test_df, cfg)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
