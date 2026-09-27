# Config reference

Every field in [`schema.yaml`](schema.yaml), tabulated with its
default and what it does. `schema.yaml` itself only marks which fields
are `required`; this page has the descriptions, so the YAML file stays
easy to scan. Copy `schema.yaml` as your starting point; anything you
leave out of your own config uses the default shown here. For the
reasoning behind the non-obvious fields and larger worked examples
(large datasets, session-grouped splits, tuning), see
[../guide/configuration.md](../guide/configuration.md).

A config needs only two things: `dataset.name` and `dataset.raw_files`
(or `train_file`+`test_file`), plus `schema.label_column`. Everything
else falls back to the default in these tables.

```yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

## `dataset`

Where the data comes from, and how it's split.

| Field | Default | Description |
|---|---|---|
| `name` | *(required)* | Short id for your dataset, e.g. `"cic-ids2018"`. Also the key `known_issue_lookup`/`schema_fingerprint_check` match against. |
| `raw_files` | *(required, or use `train_file`+`test_file`)* | Your data file(s); IDS<sup>2</sup>Eval splits them into train/test itself. |
| `train_file` / `test_file` | *(required, or use `raw_files`)* | An already-split pair, used together instead of `raw_files`. |
| `column_names` | `[]` | Set this if the CSV has no header row at all: every row is treated as data, and these names are assigned positionally, in order. Leave empty for a normal CSV with a header row. Ignored for `.parquet`, which already carries its own column names. |
| `split_ratio` | `0.8` | Train share, only used with `raw_files`. |
| `split_mode` | `random` | `random` or `grouped`. `grouped` keeps every row sharing a `group_columns` key on one side of the split. |
| `group_columns` | `[]` | Columns that define a "session"; required if `split_mode: grouped`. |
| `chunk_size` | `null` | Rows read at a time, for files too big to load whole. |
| `max_rows` | `null` | Cap total rows via reservoir sampling; needs `chunk_size` set too. |

```yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]          # or ["day1.csv", "day2.csv"] for several files
  split_ratio: 0.8
```

**File formats.** Each file can be CSV (plain, or `.gz`/`.bz2`/`.xz`/
single-member `.zip`, all inferred from the name) or `.parquet`. To
read one named file out of a *multi*-member zip without extracting it
first, use `"archive.zip::member_name.csv"`. A `.rar` archive isn't
read directly - extract it first. See
[../guide/configuration.md](../guide/configuration.md#picking-files-out-of-a-datasets-official-download)
for which files to pick from a real dataset's official download, and
worked examples for large files (`chunk_size`/`max_rows`) and
session-grouped splits (`split_mode: grouped`).

**A CSV with no header row.** Some official downloads ship this way -
NSL-KDD's original `KDDTrain+.txt`/`KDDTest+.txt` are a real example,
every row is data, and the standard KDD'99 column names exist only in
the dataset's documentation, not the file itself. Rather than editing
the file to prepend a header, declare the names in the config:

```yaml
dataset:
  name: nsl-kdd
  train_file: KDDTrain+.txt
  test_file: KDDTest+.txt
  column_names: [duration, protocol_type, service, flag, src_bytes, dst_bytes,
                 "...", label, difficulty]   # every column, in the file's own order
schema:
  label_column: label
  drop_columns: [difficulty]
```

Every column needs a name, in the file's exact order - there's no way
to name only some columns and leave the rest positional. Verified
against NSL-KDD's real data: stripping the header from the (already
correctly labeled) files this project validates against and reloading
with `column_names` set reproduces identical findings to the normal,
headered load.

**Windows paths in YAML.** A double-quoted string with a single
backslash isn't a literal backslash in YAML, it starts an escape
sequence (`\U` looks like the start of an 8-hex-digit Unicode escape,
which is why `"C:\Users\..."` fails with a `ScannerError` about "8
hexadecimal numbers"). Use forward slashes instead (`"C:/Users/.../data.csv"`,
Windows accepts these fine), or single quotes, which YAML never
escape-parses (`'C:\Users\...\data.csv'`), or double the backslashes
(`"C:\\Users\\...\\data.csv"`) if you need double quotes specifically.

## `schema`

Which columns mean what.

| Field | Default | Description |
|---|---|---|
| `label_column` | *(required)* | The binary/attack label column. |
| `attack_category_column` | `null` | Optional multi-class attack-type column. |
| `drop_columns` | `[]` | Columns to drop before training. |
| `id_like_columns` | `[]` | IP/port/MAC-like columns, checked for leakage but not auto-dropped. |
| `timestamp_column` | `null` | Used only by `temporal_leakage_check`/`temporal_realism_check`. |
| `flow_id_columns` | `[]` | Used only by `flow_group_leakage_check`, e.g. a 5-tuple. |
| `scenario_column` | `null` | Used only by `scenario_holdout_falsification`, e.g. a capture-day or attacker-host column. |
| `feature_categories` | `{}` | Used only by `feature_category_ablation_check`, mapping column name to a category label. |

```yaml
schema:
  label_column: Label
  attack_category_column: AttackType
  drop_columns: [FlowID, Timestamp]
  id_like_columns: [SrcIP, DstIP, SrcPort]
```

## `label_grouping`

| Field | Default | Description |
|---|---|---|
| `attack_type_mapping` | `{}` | Merges named attack categories into coarser ones. A **partial** mapping: anything not listed passes through unchanged. |

```yaml
label_grouping:
  attack_type_mapping:
    "DoS Hulk": DoS
    "DoS GoldenEye": DoS
    # "PortScan" and everything else not listed here stays as-is
```

## `preprocessing`

| Field | Default | Description |
|---|---|---|
| `dedup` | `true` | Remove exact duplicate rows before splitting. |
| `scaling` | `standard` | `none` \| `standard` \| `minmax` \| `robust`, or a list to compare several. |
| `sampling.binary` | `none` | `none` \| `smote` \| `smoteenn` \| `enn` \| `random_undersample`, or a list to compare several. |
| `sampling.type` | `none` | Same options, for the multi-class stage. |

```yaml
preprocessing:
  scaling: [none, standard, robust]      # compared side by side
  sampling:
    binary: [none, smote, smoteenn]
```

Scaling and sampling both run inside the same pipeline as the
classifier on every fold, never fit once beforehand - see
[../guide/configuration.md](../guide/configuration.md#tuning-and-hyperparameters)
for why that matters.

## `audit`

Which of the 27 checks run. See [../guide/checks.md](../guide/checks.md)
for what each one tests and the research behind it.

**v1, on by default, no extra setup needed:**

| Check | Default | What it does |
|---|---|---|
| `dedup_check` | `true` | Exact feature-space duplicates, within and across train/test |
| `label_conflict_check` | `true` | Same features, contradictory labels |
| `near_duplicate_class_check` | `true` | Near (not exact) duplicate features across two classes |
| `leakage_screen` | `true` | Does one feature/pair dominate a fitted model's importance? |
| `one_rule_check` | `true` | Is a single feature+threshold rule almost as good as any model? |
| `feature_auc_ranking_check` | `true` | Standalone AUC of every numeric feature, no model fit |
| `identity_column_flag` | `true` | Standalone predictive power of `schema.id_like_columns` |
| `port_protocol_shortcut_check` | `true` | No-ops unless a port + a proto-like column are both found |
| `temporal_leakage_check` | `true` | No-ops unless `schema.timestamp_column` is set |
| `temporal_realism_check` | `true` | No-ops unless `schema.timestamp_column` is set |
| `flow_group_leakage_check` | `true` | No-ops unless `schema.flow_id_columns` is set |
| `row_order_leakage_check` | `true` | Adjacent-row label clustering vs. a shuffled baseline |
| `homogeneity_test` | `true` | Is train/test proximity just inherent class homogeneity? |
| `resplit_falsification` | `true` | Needs `dataset.group_columns` set; set `false` if this dataset has no session-identifying columns |
| `scenario_holdout_falsification` | `true` | No-ops unless `schema.scenario_column` is set |
| `class_distribution_report` | `true` | Per-class counts, shares, imbalance ratio |
| `low_cardinality_warning` | `true` | No-ops unless `schema.id_like_columns` is set |
| `schema_fingerprint_check` | `true` | Matches known feature-extractor bugs by column-name fingerprint |
| `data_integrity_check` | `true` | Missing/constant/infinite values |

**v2, opt-in, need a second dataset or heavier compute:**

| Check | Default | What it does |
|---|---|---|
| `synthetic_realism_check` | `false` | Needs `reference_dataset`: real-vs-synthetic domain classifier |
| `cross_dataset_drift_check` | `false` | Needs `reference_dataset`: trains here, evaluates there |
| `cross_capture_matrix_check` | `false` | N x N accuracy matrix across `schema.scenario_column` values |
| `feature_category_ablation_check` | `false` | Accuracy cost of removing each `schema.feature_categories` group |
| `artifact_sensitivity_check` | `false` | Prediction-flip rate from reshuffling one id_like/timestamp column |
| `result_robustness_check` | `false` | Accuracy spread across split/dedup/identity-column conditions |
| `known_issue_lookup` | `false` | Curated per-dataset published problems, matched on `dataset.name` |
| `seed_sensitivity_check` | `false` | Re-fits `leakage_screen`/`one_rule_check` across a few seeds |
| `reference_dataset` | `null` | Required if `synthetic_realism_check` or `cross_dataset_drift_check` is on |

```yaml
audit:
  resplit_falsification: false   # set true + dataset.group_columns if this dataset has sessions
  known_issue_lookup: true       # free: no reference dataset needed, just dataset.name
```

## `classifiers`

Which models to benchmark.

| Field | Default | Description |
|---|---|---|
| `list` | `all` | `"all"`, or a list from: `RandomForest`, `XGBoost`, `DecisionTree`, `NaiveBayes`, `LogisticRegression`, `KNN`, `SVM`, `LDA`, `Stacking`, `Voting`, `ExtraTrees`, `HistGradientBoosting`, `AdaBoost`, `MLP` |
| `tuning` | `false` | `true` runs a `GridSearchCV` hyperparameter search per classifier, see `search_space` |
| `calibration` | `none` | `none` \| `platt` \| `isotonic` |
| `hyperparameters` | `{}` | Fixed params per classifier, used when `tuning: false` |
| `search_space` | `{}` | Grid per classifier, used when `tuning: true` |

```yaml
classifiers:
  list: [RandomForest, XGBoost]
  tuning: true
  search_space:
    RandomForest: {n_estimators: [100, 200, 300], max_depth: [10, 20, 30]}
```

## `output`

| Field | Default | Description |
|---|---|---|
| `dir` | `./output` | Where results (and the load-cache) are written. |
| `format` | `parquet` | `parquet` \| `csv`, for `output.save_preprocessed`'s files. |
| `save_preprocessed` | `true` | Also write out the cleaned train/test data. |
| `keep_runs` | `10` | Keep only the N most recent runs; `null` keeps every run. |
| `write_scorecard_plot` | `false` | Also render `scorecard.pdf`/`.png`; needs `pip install "ids2eval[plots]"`. |

```yaml
output:
  dir: ./results
  write_scorecard_plot: true
```

## `random_seed`

| Field | Default | Description |
|---|---|---|
| `random_seed` | `0` | The single source for every random step: splitting, sampling, classifier initialization. Changing it changes the result deterministically; see [../guide/configuration.md](../guide/configuration.md#reproducibility). |

## Not supported

Feature engineering (imputation, feature selection, dimensionality
reduction), hyperparameter search deeper than `classifiers.tuning`, and
multi-stage cascades. See the "scope" section on the docs site for why.
