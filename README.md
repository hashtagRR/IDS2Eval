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
train/test splits. IDS<sup>2</sup>Eval runs 27 checks that catch these
problems automatically, instead of a one-off notebook redone by hand
for every paper, and rolls the result into a citable scorecard
(`SCORECARD.html`, `SCORECARD.md`, `scorecard.json`) - "this result was
obtained on a dataset that passed the following checks," with each
check's result before and after deduplication side by side. When a
check flags, `ids2eval recommend` (CLI or a dashboard tab) suggests a
config fix for the ones that have an unambiguous one, and applies it
to a re-runnable config on request. See [guide/checks.md](guide/checks.md)
for what each check does and the scorecard's pass/fail rule.

It's narrower than general-purpose AutoML tools (PyCaret, AutoGluon,
TPOT) on purpose: no feature engineering, no algorithm-search breadth -
just the IDS-specific data-quality checks and a benchmark to compare
classifiers once the data is clean.

## Installation

Needs Python 3.10, 3.11, or 3.12 (tested in CI on all three; `pandas`/
`numpy` have no prebuilt wheels yet for 3.13+, so `pyproject.toml`
refuses those cleanly rather than falling back to a source build).

**Linux / macOS**

```bash
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
python3 -m venv venv
venv/bin/pip install -e ".[dev]"
```

**Windows**

```powershell
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
py -3.12 -m venv venv
.\venv\Scripts\pip install -e ".[dev]"
```

Use `py -3.12` (the Python Launcher, installed by every official
python.org installer), not bare `python` - see
[Windows troubleshooting](#windows-troubleshooting) below if more than
one Python is on your PATH.

The `[dev]` extra adds `pytest`/`ruff` for the test suite; drop it
(`pip install -e .`) for a runtime-only install. `pip install -e ".[dev,plots]"`
adds `matplotlib`, only needed for `output.write_scorecard_plot`.

**Run it:**

| | Linux / macOS | Windows |
|---|---|---|
| Dashboard | `venv/bin/ids2eval-dashboard` | `.\venv\Scripts\ids2eval-dashboard` |
| CLI | `venv/bin/ids2eval --config my_config.yaml` | `.\venv\Scripts\ids2eval --config my_config.yaml` |
| Tests | `venv/bin/pytest tests/ -v` | `.\venv\Scripts\pytest tests\ -v` |
| Lint | `venv/bin/ruff check ids2eval/ tests/` | `.\venv\Scripts\ruff check ids2eval/ tests/` |

The dashboard opens `http://localhost:8765` with a **New run** editor
already filled in with every config field and its default - no YAML
file to write by hand first. The CLI needs a real config; see
[Quick start](#quick-start) below for the minimal one, or
[configs/README.md](configs/README.md) for every
field. Tests and lint are exactly what CI runs on every push
(`.github/workflows/ci.yml`, Linux only for now).

**Dependencies** (`pyproject.toml`, the only source of truth - no
separate `requirements.txt`): `pyyaml`, `pandas`, `numpy`,
`scikit-learn`, `scipy`, `imbalanced-learn`, `xgboost`, `pyarrow`. All
prebuilt wheels, no compiler toolchain needed for Python 3.10-3.12 on
any of the three platforms.

### Windows troubleshooting

- **More than one Python on PATH** (MSYS2/MinGW, the Microsoft Store's
  placeholder stub, a per-user install, ...) makes bare `python`
  silently run whichever one resolves first. Run `py --list` to see
  what's actually available, and always use `py -3.12` (or whichever
  version it lists in 3.10-3.12) instead of bare `python`. Telltale
  sign this already went wrong: `python -m venv venv` "succeeds" with
  no output, but `venv\Scripts` doesn't exist afterward (an MSYS2
  Python creates a Unix-style `venv/bin` layout instead).
- **PowerShell needs the `.\` prefix** on every command above. Without
  it, PowerShell tries to resolve `venv\Scripts\pip` as a module/cmdlet
  name instead of a file path, and fails with "module could not be
  loaded" rather than "command not found." `.\` works in `cmd.exe` too.

## Quick start

```yaml
# my_config.yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

```bash
venv/bin/ids2eval --config my_config.yaml
```

Or skip writing a config file entirely: `venv/bin/ids2eval-dashboard`
opens a browser tab with the same thing pre-filled in an editor. See
[guide/usage.md](guide/usage.md) for the CLI/dashboard/output
files/programmatic API, and
[configs/README.md](configs/README.md) for every
config field with an example.

**Point it at real data**: `dataset.raw_files`/`train_file`/`test_file`
accept any IDS dataset in CSV or Parquet form - IDS<sup>2</sup>Eval doesn't
ship or require one itself. [UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
and [CIC-IDS2018](https://www.unb.ca/cic/datasets/ids-2018.html) (also
readable straight from `s3://cse-cic-ids2018/`, no credentials needed)
are two well-known ones this project validates against; see
[examples/](examples/) for real scorecards on eight of them.

## Documentation

| | |
|---|---|
| [guide/usage.md](guide/usage.md) | CLI, web UI, output files, caching, reproducing a run, programmatic API |
| [configs/README.md](configs/README.md) | Every config field, tabulated, with a default and an example |
| [guide/configuration.md](guide/configuration.md) | The reasoning behind non-obvious fields, and larger worked examples |
| [guide/checks.md](guide/checks.md) | What each of the 27 checks does, and the research behind it |
| [guide/contributing-known-issues.md](guide/contributing-known-issues.md) | How to add a curated known issue or extractor fingerprint |
| [examples/](examples/) | Real scorecards for eight widely used datasets |

Real scorecards: [UNSW-NB15](examples/unsw-nb15-scorecard),
[NSL-KDD](examples/nsl-kdd-scorecard),
[CIC-IDS2017](examples/cic-ids2017-scorecard),
[CSE-CIC-IDS2018](examples/cic-ids2018-scorecard),
[CICDDoS2019](examples/cic-ddos2019-scorecard),
[ToN-IoT](examples/ton-iot-scorecard),
[BoT-IoT](examples/bot-iot-scorecard),
[CIC-IoT2023](examples/cic-iot2023-scorecard).

## Status

Implemented, tested (319 tests, CI on Python 3.10/3.11/3.12), and
validated against real data, not just synthetic fixtures - see
[examples/](examples/) for full scorecards. Two highlights:
independently reproducing UNSW-NB15's published `sttl` TTL-topology
bias and CIC-IDS2018's published `Dst Port` leakage finding, both via
this project's own checks run against the real official distributions
rather than assumed from the literature.

Scaling and class-balancing always run inside cross-validation, never
fit once beforehand - see
[guide/configuration.md](guide/configuration.md#tuning-and-hyperparameters) for
why that matters. Growing `known_issue_lookup`'s curated table is a
good area for contributors to help with (see [guide/checks.md](guide/checks.md)).

## Provenance

IDS<sup>2</sup>Eval grew out of the dataset evaluation and auditing
code developed during research on machine-learning-based network
intrusion detection. It generalizes portions of that research code
into a dataset-independent toolkit for examining IDS datasets,
evaluation pipelines, and classifier behaviour.

The originating research is described in two related manuscripts
currently in preparation:

* "Auditing Network Intrusion Detection Benchmarks: A
  Falsification-Oriented Evaluation of UNSW-NB15 and CSE-CIC-IDS2018"
* "Confidence-Routed Staged Detection for Network Intrusion Detection"

The first manuscript develops and applies the dataset-auditing
methodology from which much of IDS<sup>2</sup>Eval originated. The
second evaluates a staged intrusion-detection architecture built
within the broader research codebase. IDS<sup>2</sup>Eval does not
implement that staged architecture.

Links to the papers will be added when publicly available.

## License

AGPL-3.0 - see [LICENSE](LICENSE).
