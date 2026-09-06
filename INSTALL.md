# Installing IDS2Eval

## Prerequisites

Python 3.10 or later (tested in CI on 3.10, 3.11, and 3.12).

## Setup

```bash
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
python3 -m venv venv
venv/bin/pip install -e ".[dev]"
```

The `[dev]` extra adds `pytest` and `ruff`, used for the test suite and
linting — skip it (`pip install -e .`) for a runtime-only install.

This installs the `ids2eval` console script into the venv:

```bash
venv/bin/ids2eval --config my_config.yaml
```

## Verify

```bash
venv/bin/pytest tests/ -v
venv/bin/ruff check ids2eval/ tests/
```

Both should pass clean — this is exactly what CI runs on every push
(`.github/workflows/ci.yml`).

## Dependencies

Declared in `pyproject.toml` (the single source of truth — there's no
separate `requirements.txt` to drift out of sync with it): `pyyaml`,
`pandas`, `numpy`, `scikit-learn`, `scipy`, `imbalanced-learn`,
`xgboost`, `pyarrow`. All install from prebuilt wheels on Linux/macOS/
Windows for Python 3.10–3.12 — no compiler toolchain needed.

## Real datasets used in validation

Not part of the install — IDS2Eval doesn't ship or require any
dataset. The real-data validation referenced in the README used:

- [UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset) — pre-split train/test CSVs
- [CIC-IDS2018](https://www.unb.ca/cic/datasets/ids-2018.html) — the official "Processed Traffic Data for ML Algorithms" CSVs, publicly readable from `s3://cse-cic-ids2018/` with no credentials required

Point `dataset.raw_files`/`train_file`/`test_file` in your own config
at wherever you keep these (or any other IDS dataset in CSV form) —
see [USAGE.md](USAGE.md) and [CONFIGURATION.md](CONFIGURATION.md).
