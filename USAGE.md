# Using IDS2Eval

## CLI

```bash
ids2eval --config my_config.yaml
```

(or `python -m ids2eval --config my_config.yaml` if you haven't
installed the console script — see [INSTALL.md](INSTALL.md).)

Flags:

| Flag | Effect |
|---|---|
| `--skip-audit` | Skip both audit passes (before and after dedup) |
| `--skip-benchmark` | Skip classifier benchmarking |

Everything else is driven by the config file — see
[CONFIGURATION.md](CONFIGURATION.md) for the full surface and
[configs/schema.yaml](configs/schema.yaml) for the exhaustive,
commented reference.

## What actually runs

Traced from `ids2eval/cli.py`'s `main()`, in order:

1. **Load config**, validated against the schema
2. **Load + split** the dataset — from cache if a previous run's
   fingerprint still matches, otherwise from `raw_files`/`train_file`+
   `test_file`, then `label_grouping.attack_type_mapping` is applied
3. **Hard-fail validation** (`dataset.validate_loaded`) — duplicate
   column names, a train/test schema sharing no feature columns, or an
   empty split raise immediately, before anything else runs
4. **Create this run's directory** (`output.dir/runs/<timestamp>/`),
   write `environment.json`, `resolved_config.json`,
   `dataset_fingerprint.json`
5. **Audit** (unless `--skip-audit`) — writes `audit_report_before.json`
6. **Dedup** (if `preprocessing.dedup`) — then **audit again**, writing
   `audit_report_after.json`
7. **Write preprocessed data** (if `output.save_preprocessed`) —
   `train.<fmt>`/`test.<fmt>`
8. **Benchmark** (unless `--skip-benchmark`) — writes
   `benchmark_results.csv` and `benchmark_details.json`
9. **Prune old runs** beyond `output.keep_runs` (never touches the cache)

## Output files

All written under `output.dir/runs/<timestamp>/` (a fresh directory
every run — nothing gets silently overwritten):

| File | Contents |
|---|---|
| `audit_report_before.json` | All enabled audit findings, computed before dedup |
| `audit_report_after.json` | Same, after dedup (only if `preprocessing.dedup` is on) |
| `train.<fmt>` / `test.<fmt>` | The preprocessed data (parquet by default) |
| `benchmark_results.csv` | One row per (stage, sampling strategy, classifier): accuracy, weighted F1, AUC, train/inference time |
| `benchmark_details.json` | Per-row confusion matrix, per-class precision/recall/F1, feature importance (where the classifier supports it), winning hyperparameters (if `classifiers.tuning` ran), and each stage's class distribution before/after sampling |
| `environment.json` | Python version, platform, `ids2eval`'s own version/git commit, key package versions |
| `resolved_config.json` | The fully resolved config (your YAML merged onto defaults) — one of the three things (with the dataset fingerprint and the seed) needed to reproduce a run |
| `dataset_fingerprint.json` | Row/feature counts, class distributions, and a real content hash of train/test — proof two runs used identical data, not just "probably the same file" |
| `run_status.json` | `completed`, or `failed` with which stage and the error |

`output.dir/.cache/` sits outside the `runs/` tree on purpose — it's
the load-cache (see below), reused across runs, and untouched by
`output.keep_runs` pruning.

## Reproducing a run exactly

Every seed in the data-loading and benchmarking pipeline (train/test
split, reservoir sampling, SMOTE/etc., classifier initialization,
benchmark subsampling) derives from the single `random_seed` config
value. Combined with `resolved_config.json` and
`dataset_fingerprint.json`, a run is fully specified — same seed, same
data, same config reproduces identical accuracy/F1/AUC.

## Caching

The load+split+label-grouping step — the expensive part on a large
dataset, per measurement against real CIC-IDS2018 data — is cached
under `output.dir/.cache/`. A fingerprint over the input files
(path/size/mtime) and the config fields that determine this step
(split, chunking, schema, label grouping, `ids2eval`'s own version)
auto-invalidates a stale cache; there's no manual flag to remember.
Scaling and sampling are deliberately **not** cached — they run on an
already-capped sample and are cheap, while being exactly the settings
people iterate on most while benchmarking.

## Programmatic usage

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

`run_audit()` must run before `dataset.dedup()` — `dedup_check`
reports duplication already present in the data, and `dedup()` would
remove it first.
