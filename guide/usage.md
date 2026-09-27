# Using IDS<sup>2</sup>Eval

## CLI

```bash
ids2eval --config my_config.yaml
```

(or `python -m ids2eval --config my_config.yaml` if you haven't
installed the console script; see [the README](../README.md#installation).)

Flags:

| Flag | Effect |
|---|---|
| `--skip-audit` | Skip both audit passes (before and after dedup) |
| `--skip-benchmark` | Skip classifier benchmarking |

`ids2eval --config ...` is shorthand for `ids2eval run --config ...`;
three other subcommands are available:

```bash
ids2eval validate-config --config my_config.yaml   # check a config for errors, no data loaded
ids2eval cite path/to/a/run/directory              # print a BibTeX citation from that run's scorecard
ids2eval compare-datasets a.yaml b.yaml            # check whether two configs load equivalent data
```

`compare-datasets` loads both configs' data and compares schema, row
counts, label distribution, and content, useful when two configs claim
to point at "the same" dataset (an official release and a third-party
mirror, say) and you want to know whether they actually agree.

## Web UI (dashboard)

```bash
ids2eval-dashboard
```

No config file needed to start: this opens `http://localhost:8765`
with a **New run** editor already filled in with
[`configs/schema.yaml`](../configs/schema.yaml)'s full reference,
every field, its real default, and a one-line explanation, not a
stripped-down subset. `--config` below is optional, for prefilling the
editor with a config you already have or listing runs from its
`output.dir`, not a requirement to launch the dashboard at all. A
small local web app (standard library only, no
extra dependencies):

- **Runs**: every run under the listed output directories, newest
  first, with its verdict; each run shows its `SCORECARD.html`, its
  benchmark results sorted by weighted F1, links to every artifact, and
  a **Cite** button (the same BibTeX `ids2eval cite` prints)
- **New run**: edit a YAML config, validate it (the same validation
  the CLI does), and launch it with a live log. A run is a real
  `python -m ids2eval` subprocess, so it behaves exactly like the CLI;
  relative paths resolve against the directory the UI was started in.
  One run at a time.
- **Compare datasets**: paste two configs and check whether they load
  equivalent data, the same comparison as `ids2eval compare-datasets`,
  over pasted YAML instead of two file paths.

| Flag | Effect |
|---|---|
| `--config PATH` | Optional: prefill the editor, and list runs from its `output.dir`. A missing or invalid path falls back to the starter config with a logged warning, never a crash |
| `--output DIR` | Also list runs from this `output.dir` (repeatable; default `./output`) |
| `--host` / `--port` | Bind address, default `127.0.0.1:8765` |
| `--no-browser` | Don't open a browser tab |

It's meant for your own machine: it binds to localhost and refuses
requests with a foreign `Host` or `Origin`. Anyone who can reach the
port can run a config (and so read files the config points at), so
don't bind it to a public interface. The dashboard's code, API and
troubleshooting notes are in [ids2eval/dashboard/](../ids2eval/dashboard/README.md).

## Configuration

Everything else is driven by the config file. See
[configuration.md](configuration.md) for the full surface and
[configs/schema.yaml](../configs/schema.yaml) for the exhaustive,
commented reference.

## What actually runs

Traced from `ids2eval/cli.py`'s `main()`, in order:

1. **Load config**, validated against the schema
2. **Load + split** the dataset: from cache if a previous run's
   fingerprint still matches, otherwise from `raw_files`/`train_file`+
   `test_file`, then `label_grouping.attack_type_mapping` is applied
3. **Hard-fail validation** (`dataset.validate_loaded`): duplicate
   column names, a train/test schema sharing no feature columns, or an
   empty split raise immediately, before anything else runs
4. **Create this run's directory** (`output.dir/runs/<timestamp>/`),
   write `environment.json`, `resolved_config.json`,
   `dataset_fingerprint.json`
5. **Audit** (unless `--skip-audit`): writes `audit_report_before.json`
6. **Dedup** (if `preprocessing.dedup`), then **audit again**, writing
   `audit_report_after.json`
7. **Scorecard** (unless `--skip-audit`): rolls both audit passes up
   into `SCORECARD.html`/`SCORECARD.md`/`scorecard.json` (verdict judged
   on the final pass), plus `scorecard.pdf`/`.png` if
   `output.write_scorecard_plot` is on
8. **Write preprocessed data** (if `output.save_preprocessed`):
   `train.<fmt>`/`test.<fmt>`
9. **Benchmark** (unless `--skip-benchmark`): writes
   `benchmark_results.csv` and `benchmark_details.json`
10. **Prune old runs** beyond `output.keep_runs` (never touches the cache)

## Output files

All written under `output.dir/runs/<timestamp>/` (a fresh directory
every run, nothing gets silently overwritten):

| File | Contents |
|---|---|
| `audit_report_before.json` | All enabled audit findings, computed before dedup |
| `audit_report_after.json` | Same, after dedup (only if `preprocessing.dedup` is on) |
| `SCORECARD.html` / `SCORECARD.md` / `scorecard.json` | A citable pass/fail rollup of the findings above, with before/after-dedup results side by side. See [checks.md](checks.md#the-scorecard). The HTML is self-contained: open it from disk, or print it to PDF |
| `scorecard.pdf` / `scorecard.png` | A chart version of the scorecard, only if `output.write_scorecard_plot` is on (needs `pip install "ids2eval[plots]"`) |
| `train.<fmt>` / `test.<fmt>` | The preprocessed data (parquet by default) |
| `benchmark_results.csv` | One row per (stage, scaling, sampling strategy, classifier): accuracy, weighted F1, macro F1, AUC, train/inference time |
| `per_class_metrics.csv` | Per-class precision/recall/F1/support, the same numbers nested in `benchmark_details.json`'s `per_class_report`, flattened so a summary table can scan it directly |
| `benchmark_details.json` | Per-row confusion matrix, per-class precision/recall/F1, feature importance (where the classifier supports it), winning hyperparameters (if `classifiers.tuning` ran), and each stage's class distribution before/after sampling |
| `environment.json` | Python version, platform, `ids2eval`'s own version/git commit, key package versions |
| `resolved_config.json` | The fully resolved config (your YAML merged onto defaults): one of the three things (with the dataset fingerprint and the seed) needed to reproduce a run |
| `dataset_fingerprint.json` | Row/feature counts, class distributions, the loaded column schema, a real content hash of train/test, and each source file's own size and SHA256: proof two runs used identical data, not just "probably the same file" (see `ids2eval compare-datasets` above for comparing two datasets against each other) |
| `run_status.json` | `completed`, or `failed` with which stage and the error |

`output.dir/.cache/` sits outside the `runs/` tree on purpose. It's
the load-cache (see below), reused across runs, and untouched by
`output.keep_runs` pruning.

## Reproducing a run exactly

Every seed in the data-loading and benchmarking pipeline (train/test
split, reservoir sampling, SMOTE/etc., classifier initialization,
benchmark subsampling) derives from the single `random_seed` config
value. Combined with `resolved_config.json` and
`dataset_fingerprint.json`, a run is fully specified: same seed, same
data, same config reproduces identical accuracy/F1/AUC.

## Caching

The load+split+label-grouping step, the expensive part on a large
dataset, per measurement against real CIC-IDS2018 data, is cached
under `output.dir/.cache/`. A fingerprint over the input files
(path/size/mtime) and the config fields that determine this step
(split, chunking, schema, label grouping, `ids2eval`'s own version)
auto-invalidates a stale cache; there's no manual flag to remember.
Scaling and sampling are deliberately **not** cached. They run on an
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

`run_audit()` must run before `dataset.dedup()`: `dedup_check`
reports duplication already present in the data, and `dedup()` would
remove it first.
