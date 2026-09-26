# IDS<sup>2</sup>Eval

**[hashtagRR.github.io/IDS2Eval](https://hashtagRR.github.io/IDS2Eval)**

*IDS<sup>2</sup> - the name works both ways: **I**ntrusion **D**etection
**S**ystems, and **I**ntrusion **D**ata **S**ets. (GitHub repo names
can't do superscripts, hence `IDS2Eval`.)*

A config-driven toolkit that checks a network intrusion detection
(NIDS) dataset for quality problems, then benchmarks classifiers on
it - no code required, just a YAML file.

Most published NIDS results are evaluated on datasets whose quality is
taken on faith: duplicate rows, leaked features, near-identical
train/test splits. IDS<sup>2</sup>Eval runs 18 checks that catch these
problems automatically, instead of a one-off notebook redone by hand
for every paper, and rolls the result into a citable scorecard
(`SCORECARD.html`, `SCORECARD.md`, `scorecard.json`) - "this result was
obtained on a dataset that passed the following checks," with each
check's result before and after deduplication side by side. See
[guide/checks.md](guide/checks.md) for what each check does and the
scorecard's pass/fail rule.

It's narrower than general-purpose AutoML tools (PyCaret, AutoGluon,
TPOT) on purpose: no feature engineering, no algorithm-search breadth -
just the IDS-specific data-quality checks and a benchmark to compare
classifiers once the data is clean.

## Quick start

```bash
python3 -m venv venv
venv/bin/pip install -e .
venv/bin/ids2eval --config my_config.yaml
```

Or run it from a browser - a small local dashboard ([ids2eval/dashboard](ids2eval/dashboard)) - to browse runs, read
their scorecards and benchmark results, and launch new runs from a
YAML config:

```bash
venv/bin/ids2eval-dashboard --config my_config.yaml   # opens http://localhost:8765
```

```yaml
# my_config.yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

See [Installation](#installation) below for full setup,
[guide/usage.md](guide/usage.md) for the CLI/output files/programmatic
API, and [guide/configuration.md](guide/configuration.md) for how to
customize a config (field list:
[`configs/schema.yaml`](configs/schema.yaml)).

## Installation

Needs Python 3.10 or later (tested in CI on 3.10, 3.11, and 3.12).

**Linux / macOS**

```bash
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
python3 -m venv venv
venv/bin/pip install -e ".[dev]"
```

**Windows (PowerShell or cmd)**

```powershell
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
python -m venv venv
venv\Scripts\pip install -e ".[dev]"
```

The `[dev]` extra adds `pytest` and `ruff`, used for the test suite and
linting; skip it (`pip install -e .`) for a runtime-only install. A
separate `[plots]` extra (`pip install -e ".[dev,plots]"`) adds
`matplotlib`, needed only if you turn on `output.write_scorecard_plot`
(see [guide/usage.md](guide/usage.md)).

This installs two console scripts into the venv: the CLI, and the
local dashboard (see
[guide/usage.md#web-ui-dashboard](guide/usage.md#web-ui-dashboard)).
On Windows they're `venv\Scripts\ids2eval` and
`venv\Scripts\ids2eval-dashboard`; on Linux/macOS, `venv/bin/ids2eval`
and `venv/bin/ids2eval-dashboard`.

**Verify:**

```bash
venv/bin/pytest tests/ -v          # Windows: venv\Scripts\pytest tests\ -v
venv/bin/ruff check ids2eval/ tests/
```

Both should pass clean. This is exactly what CI runs on every push
(`.github/workflows/ci.yml`), on Linux only; the dependencies below all
ship prebuilt wheels for Windows too, but Windows itself isn't covered
by CI yet.

**Dependencies**, declared in `pyproject.toml` (the single source of
truth, there's no separate `requirements.txt` to drift out of sync
with it): `pyyaml`, `pandas`, `numpy`, `scikit-learn`, `scipy`,
`imbalanced-learn`, `xgboost`, `pyarrow`. All install from prebuilt
wheels on Linux/macOS/Windows for Python 3.10-3.12, no compiler
toolchain needed. `matplotlib` is not in this list on purpose, it's
the `[plots]` extra above, only needed for `scorecard.pdf`/`scorecard.png`.

**Real datasets used in validation** (not part of the install,
IDS<sup>2</sup>Eval doesn't ship or require any dataset):

- [UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset): pre-split train/test CSVs
- [CIC-IDS2018](https://www.unb.ca/cic/datasets/ids-2018.html): the official "Processed Traffic Data for ML Algorithms" CSVs, publicly readable from `s3://cse-cic-ids2018/` with no credentials required

Point `dataset.raw_files`/`train_file`/`test_file` in your own config
at wherever you keep these (or any other IDS dataset in CSV form); see
[guide/usage.md](guide/usage.md) and
[guide/configuration.md](guide/configuration.md).

## Documentation

| | |
|---|---|
| [guide/usage.md](guide/usage.md) | CLI, web UI, output files, caching, reproducing a run, programmatic API |
| [guide/configuration.md](guide/configuration.md) | Config walkthrough with worked examples |
| [guide/checks.md](guide/checks.md) | What each of the 19 checks does, and the research behind it |
| [guide/contributing-known-issues.md](guide/contributing-known-issues.md) | How to add a curated known issue or extractor fingerprint |
| [configs/schema.yaml](configs/schema.yaml) | Every field, one line each - copy it as your starting point |
| [examples/](examples/) | Real scorecards for seven widely used datasets: [UNSW-NB15](examples/unsw-nb15-scorecard), [NSL-KDD](examples/nsl-kdd-scorecard), [CIC-IDS2017](examples/cic-ids2017-scorecard), [CSE-CIC-IDS2018](examples/cic-ids2018-scorecard), [CICDDoS2019](examples/cic-ddos2019-scorecard), [ToN-IoT](examples/ton-iot-scorecard), [BoT-IoT](examples/bot-iot-scorecard) |

## Status

Implemented, tested (218 tests, CI on Python 3.10/3.11/3.12), and
validated against real data - not just synthetic fixtures:

- **UNSW-NB15** (full dataset) - audit + 5 classifiers, including
  `tuning: true` with a multi-strategy sampling comparison, ran
  cleanly end to end. Feature importance independently reproduced the
  published `sttl` TTL-topology bias; the before/after-dedup audit
  surfaced a real finding (class balance shifted from 2:1 to roughly
  1:1 after removing duplicates - they were disproportionately one
  class). Full real-data scorecard, checks, and chart:
  [examples/unsw-nb15-scorecard](examples/unsw-nb15-scorecard)
- **CIC-IDS2018** (official 10-file, 16.2M-row distribution) -
  chunked loading + reservoir sampling kept peak memory at 3.0GB on a
  7.8GB-RAM machine; `identity_column_flag` independently reproduced
  the published `Dst Port` leakage finding

Scaling and class-balancing always run inside cross-validation, never
fit once beforehand - see
[guide/configuration.md](guide/configuration.md#tuning-and-hyperparameters) for
why that matters.

`known_issue_lookup`'s two seed entries demonstrate the mechanism -
growing the curated table is a good area for contributors to help with
(see [guide/checks.md](guide/checks.md)).

## Provenance

IDS2Eval grew out of the dataset evaluation and auditing code developed during research on machine-learning-based network intrusion detection. It generalizes portions of that research code into a dataset-independent toolkit for examining IDS datasets, evaluation pipelines, and classifier behaviour.

The originating research is described in two related manuscripts currently in preparation:

* "Auditing Network Intrusion Detection Benchmarks: A Falsification-Oriented Evaluation of UNSW-NB15 and CSE-CIC-IDS2018"
* "Confidence-Routed Staged Detection for Network Intrusion Detection"

The first manuscript develops and applies the dataset-auditing methodology from which much of IDS2Eval originated. The second evaluates a staged intrusion-detection architecture built within the broader research codebase. IDS2Eval does not implement that staged architecture.

Links to the papers will be added when publicly available.

## License

AGPL-3.0 - see [LICENSE](LICENSE).
