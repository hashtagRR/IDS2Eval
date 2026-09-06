# Configuring IDS2Eval

Every field, its default, and its valid options is documented directly
in [`configs/schema.yaml`](configs/schema.yaml) — that file is the
exhaustive reference, kept in sync with `ids2eval/config.py`'s
validation on purpose. This page is a walkthrough of the config
surface and a few worked examples, not a duplicate of the schema.

## Minimal config

```yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

Everything else falls back to a documented default. `dataset.name` is
required (it's the key `known_issue_lookup`/`schema_fingerprint_check`
match against), and you need either `raw_files` (IDS2Eval splits it
itself) or a `train_file`+`test_file` pair (already split).

## Config sections, at a glance

| Section | Governs |
|---|---|
| `dataset` | Where the data comes from, how it's split, chunked reading/reservoir sampling for large files |
| `schema` | Which columns are the label, the attack-category column, and which to drop or treat as identity columns |
| `label_grouping` | Collapsing raw attack categories into coarser ones |
| `preprocessing` | Dedup, scaling, class-balancing strategy (or strategies, to compare) |
| `audit` | Which of the 12 checks run, and the reference dataset the two v2 checks need |
| `classifiers` | Which of the 14 classifiers to benchmark, tuning, calibration, per-classifier hyperparameters/search spaces |
| `output` | Where results go, output format, run retention |
| `random_seed` | The single source for every seed in the pipeline |

## Large datasets

```yaml
dataset:
  raw_files: ["day1.csv", "day2.csv", "..."]
  chunk_size: 100000    # rows read at a time - bounds memory during parsing
  max_rows: 500000      # reservoir-sampled cap on the final in-memory dataset
```

`chunk_size` alone only bounds memory *during* parsing — every
downstream step still needs one consolidated array, so it doesn't by
itself prevent OOM on a dataset bigger than RAM. `max_rows` is what
actually does: a uniform reservoir sample across the whole row stream,
verified on the real, official CIC-IDS2018 distribution (16.2M rows,
10 files) to keep peak memory around 3GB on a 7.8GB-RAM machine.

## Collapsing attack categories

```yaml
schema:
  attack_category_column: AttackType
label_grouping:
  attack_type_mapping:
    "DoS Hulk": DoS
    "DoS GoldenEye": DoS
```

A **partial** mapping: only the categories named as keys merge: every
other category (e.g. `PortScan`) passes through unchanged, so you
don't have to enumerate every class that should stay as-is.

## Comparing sampling strategies

```yaml
preprocessing:
  sampling:
    binary: [none, smote, smoteenn]
```

Benchmarks every selected classifier once per strategy, reporting
each as its own row in `benchmark_results.csv` plus a class-
distribution comparison (original vs. each strategy's result) in
`benchmark_details.json`. Scaling doesn't support this yet — it's
still single-valued.

## Tuning and hyperparameters

```yaml
classifiers:
  list: [RandomForest, XGBoost]
  tuning: true
  calibration: platt
  search_space:
    RandomForest: {n_estimators: [100, 200, 300], max_depth: [10, 20, 30]}
  hyperparameters:
    XGBoost: {learning_rate: 0.05}
```

`tuning: true` runs `GridSearchCV` per classifier (skipped for the
three fixed no-tune candidates — NaiveBayes, Stacking, Voting);
`hyperparameters` sets fixed values used when `tuning` is off.
Scaling and sampling run *inside* the same pipeline as the classifier
in both cases — see the correctness note in the main
[README](README.md#correctness-note--scalingsampling-and-cross-validation)
for why that isn't just an implementation detail.

## Auditing against a reference dataset

```yaml
audit:
  synthetic_realism_check: true
  cross_dataset_drift_check: true
  reference_dataset: /path/to/a/second/dataset.csv
```

Both v2 checks need a second dataset in the same schema — a
real-traffic sample for realism, or an independent dataset for drift.
`known_issue_lookup` (the third v2 check) needs neither, just a
`dataset.name` match.

## Reproducibility

```yaml
random_seed: 42
```

Every split/sampling/classifier-init seed in the data and benchmark
pipeline derives from this one value (default `0`) — changing it
changes the result deterministically, and correctly invalidates the
load-cache. It does not reach the audit checks' own internal
diagnostic sampling (deliberate — those are exploratory signals, not
part of the reported experimental result) or a couple of nested
sub-estimators (AdaBoost's fixed depth-1 stump, Stacking/Voting's base
learners).
