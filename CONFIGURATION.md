# Configuring IDS<sup>2</sup>Eval

[`configs/schema.yaml`](configs/schema.yaml) lists every field, its
default, and its valid options with a short one-line comment each —
copy it as your starting point. This page is the reasoning behind the
non-obvious fields, plus worked examples, for when the one-liner isn't
enough.

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
match against), and you need either `raw_files` (IDS<sup>2</sup>Eval splits it
itself) or a `train_file`+`test_file` pair (already split).

## Config sections, at a glance

| Section | Governs |
|---|---|
| `dataset` | Where the data comes from, how it's split, chunked reading/reservoir sampling for large files |
| `schema` | Which columns are the label, the attack-category column, and which to drop or treat as identity columns |
| `label_grouping` | Collapsing raw attack categories into coarser ones |
| `preprocessing` | Dedup, and scaling/class-balancing strategy — either can be a list, to compare |
| `audit` | Which of the 12 checks run, and the reference dataset the two v2 checks need |
| `classifiers` | Which of the 14 classifiers to benchmark, tuning, calibration, per-classifier hyperparameters/search spaces |
| `output` | Where results go, output format, run retention, optional scorecard chart |
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

## Splitting on sessions, not randomly

```yaml
dataset:
  split_mode: grouped
  group_columns: [SrcIP, DstIP, DstPort, Protocol]
```

A plain random split can put two rows from the same
session/conversation on opposite sides of train/test, which leaks
information across the split. `grouped` keeps every row that shares a
`group_columns` key on the same side. There's no universal set of
column names for this across IDS datasets — pick whatever columns
identify a session in yours (source/destination IP and port are a
common choice for flow-based datasets).

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

## Comparing sampling and scaling strategies

```yaml
preprocessing:
  scaling: [none, standard, robust]
  sampling:
    binary: [none, smote, smoteenn]
```

Either field accepts a single value (the default) or a list. Give both
a list and every selected classifier is benchmarked once per
`scaling` × `sampling` combination — 3 × 3 = 9 runs per classifier
here — each its own row in `benchmark_results.csv` with `scaling` and
`sampling` columns to tell them apart. `benchmark_details.json` adds a
class-distribution comparison (original vs. each sampling strategy's
result) — scaling doesn't change class counts, so it isn't part of
that comparison.

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

**Why scaling and sampling run inside the pipeline, not before it.**
Both run inside the same `imblearn` pipeline as the classifier, every
time — not fit once up front — so `tuning`'s and `calibration`'s
internal cross-validation folds each redo scaling/sampling
independently. Fitting a scaler or a sampler like SMOTE once on the
whole training set, and only then handing the result to
`GridSearchCV`/`CalibratedClassifierCV`, would let their internal
folds see data transformed using information from other,
supposedly-held-out folds. SMOTE makes this concrete: a fold's
synthetic rows could be interpolated from real neighbors that landed
in a *different* fold, so that fold's "held out" data was never truly
unseen.

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

## Rendering the scorecard as a chart

```yaml
output:
  write_scorecard_plot: true
```

Off by default — turning it on adds `scorecard.pdf` (vector, for citing
directly in a paper) and `scorecard.png` (raster, embedded automatically
in `SCORECARD.md` so the chart previews on GitHub) alongside the existing
`scorecard.json`/`SCORECARD.md`. This needs `matplotlib`, which is **not**
a core dependency — `pip install "ids2eval[plots]"` first, or config
validation fails immediately with that same instruction rather than
crashing partway through a run. See
[AUDIT_CHECKS.md](AUDIT_CHECKS.md#the-scorecard) for what's actually
plotted.

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
