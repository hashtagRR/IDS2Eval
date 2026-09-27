# Configuring IDS<sup>2</sup>Eval

[configs/README.md](../configs/README.md) lists every field, its
default, and a short description, tabulated. This page is the reasoning
behind the non-obvious fields, plus larger worked examples, for when
the reference's one-liner isn't enough.

## Picking files out of a dataset's official download

A real dataset's official archive is rarely just the training data - a
column/feature reference, per-scenario raw capture files, an event
log, and the actual train/test pair are often all zipped together.
Nothing here scans a zip or a folder for you: name the exact file(s)
you want, and IDS<sup>2</sup>Eval reads only those.

The rule this project's own example configs (UNSW-NB15, NSL-KDD, ...)
all follow: if the archive already ships a pre-split, pre-labeled
train/test pair (file names containing something like `training-set`/
`testing-set`, `Train+`/`Test+`), use exactly those two as
`train_file`+`test_file`. Otherwise, use only the actual per-scenario
data files as `raw_files` and let IDS<sup>2</sup>Eval split them itself -
never a features/schema reference, an event log, or anything else that
isn't itself a table of flow records.

UNSW-NB15's official zip is a concrete case: it contains
`NUSW-NB15_features.csv` (a column-name reference, not data),
`UNSW-NB15_1.csv` through `_4.csv` (the four raw, unlabeled capture
files), `UNSW-NB15_LIST_EVENTS.csv` (an event log), and
`UNSW_NB15_training-set.csv` / `UNSW_NB15_testing-set.csv` (the
official pre-split, pre-labeled pair). Since the train/test pair
exists, that's what to use, and nothing else in the zip:

```yaml
dataset:
  name: unsw-nb15
  train_file: UNSW_NB15_training-set.csv
  test_file: UNSW_NB15_testing-set.csv
```

**Without extracting the zip first**, name the member directly with
`archive.zip::member_name.csv` (a literal `::` separates the archive
from the file inside it):

```yaml
dataset:
  name: unsw-nb15
  train_file: "UNSW-NB15.zip::UNSW_NB15_training-set.csv"
  test_file: "UNSW-NB15.zip::UNSW_NB15_testing-set.csv"
```

This only works for one explicitly named member; pointing `raw_files`
at the whole zip with no `::member` isn't supported; a multi-file
archive has no single obvious member to pick, and a `.rar` archive
needs an external `unrar`/`7z` binary with no reliable cross-platform
story. Extract either yourself first if a `::` member reference isn't
an option.

## A dataset with no header row

```yaml
dataset:
  column_names: [duration, protocol_type, "...", label]
```

Some official downloads are entirely headerless: the file is nothing
but data rows, and the column names live only in a paper or a
`.names` companion file, not the CSV itself. NSL-KDD's original
`KDDTrain+.txt`/`KDDTest+.txt` are exactly this shape. Without
`dataset.column_names`, IDS<sup>2</sup>Eval would read row 0 as a header
and silently lose that row of real traffic, then infer nonsense column
names from whatever values happened to be in it. Setting
`column_names` tells the loader the opposite: every row, including row
0, is data, and these are the names, assigned positionally in the
file's own column order. It has to be every column, in order - there's
no way to name a handful of columns and leave the rest positional -
and it's ignored for `.parquet`, which already carries its own schema
in the file and has no such ambiguity to resolve.

**Get the column count right for the specific file.** A `column_names`
list built for one release of a dataset doesn't necessarily match
another release of the "same" dataset: UNSW-NB15's four raw capture
files (`UNSW-NB15_1.csv`...`_4.csv`) have 49 columns, while its
separate pre-split `training-set`/`testing-set` files have 45 - two
real, differently-shaped releases of the same dataset. Pointing
`column_names` built for one at the other raises a clear error
(`dataset.column_names has N names, but this file's rows don't have
that many fields`) rather than pandas' own cryptic tokenizing error,
but the fix is still the same either way: check the actual file you're
loading, not just the dataset's name.

## Large datasets

```yaml
dataset:
  raw_files: ["day1.csv", "day2.csv", "..."]
  chunk_size: 100000    # rows read at a time - bounds memory during parsing
  max_rows: 500000      # reservoir-sampled cap on the final in-memory dataset
```

`chunk_size` alone only bounds memory *during* parsing. Every
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
column names for this across IDS datasets. Pick whatever columns
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
`scaling` × `sampling` combination (3 × 3 = 9 runs per classifier
here), each its own row in `benchmark_results.csv` with `scaling` and
`sampling` columns to tell them apart. `benchmark_details.json` adds a
class-distribution comparison (original vs. each sampling strategy's
result). Scaling doesn't change class counts, so it isn't part of
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
three fixed no-tune candidates: NaiveBayes, Stacking, Voting).
`hyperparameters` sets fixed values used when `tuning` is off.

**Why scaling and sampling run inside the pipeline, not before it.**
Both run inside the same `imblearn` pipeline as the classifier, every
time, not fit once up front, so `tuning`'s and `calibration`'s
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

Only two of the eight v2 checks need `reference_dataset`: a real-traffic
sample for `synthetic_realism_check`, or an independent dataset for
`cross_dataset_drift_check`, both in the same schema. `known_issue_lookup`
needs neither, just a `dataset.name` match, and `seed_sensitivity_check`
needs neither either, just re-fitting `leakage_screen`/`one_rule_check`
across a few seeds. See [checks.md](checks.md) for what
each check does.

## Catching timestamp-driven shortcuts

```yaml
schema:
  timestamp_column: Timestamp
```

`temporal_leakage_check` (v1, no-ops unless this is set) tests whether
the timestamp column alone predicts the label. Datasets collected as
scenario-specific time windows (attack X launched 2-3pm, attack Y
3-4pm, ...) let a model win by learning when an attack happened rather
than what it looked like. There's no universal column name to detect
automatically, the way `id_like_columns` is user-declared too, so this
needs to be pointed at explicitly.

## Rendering the scorecard as a chart

```yaml
output:
  write_scorecard_plot: true
```

Off by default. Turning it on adds `scorecard.pdf` (vector, for citing
directly in a paper) and `scorecard.png` (raster, embedded automatically
in `SCORECARD.md` so the chart previews on GitHub) alongside the existing
`scorecard.json`/`SCORECARD.md`. This needs `matplotlib`, which is **not**
a core dependency. Run `pip install "ids2eval[plots]"` first, or config
validation fails immediately with that same instruction rather than
crashing partway through a run. See
[checks.md](checks.md#the-scorecard) for what's actually
plotted.

## Reproducibility

```yaml
random_seed: 42
```

Every split/sampling/classifier-init seed in the data and benchmark
pipeline derives from this one value (default `0`). Changing it
changes the result deterministically, and correctly invalidates the
load-cache. It does not reach the audit checks' own internal
diagnostic sampling (deliberate: those are exploratory signals, not
part of the reported experimental result, and `seed_sensitivity_check`
deliberately re-fits across its own fixed seeds 0-4 regardless of
`random_seed`, to test robustness to seed choice specifically) or a
couple of nested
sub-estimators (AdaBoost's fixed depth-1 stump, Stacking/Voting's base
learners).
