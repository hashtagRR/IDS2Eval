# Installing IDS<sup>2</sup>Eval

IDS<sup>2</sup>Eval needs Python 3.10, 3.11 or 3.12, and CI tests all three. `pandas` and
`numpy` have no prebuilt wheels yet for 3.13 and later, so `pyproject.toml` refuses those
versions instead of falling back to a source build.

## Linux and macOS

```bash
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
python3 -m venv venv
venv/bin/pip install -e ".[dev]"
```

## Windows

```powershell
git clone https://github.com/hashtagRR/IDS2Eval.git
cd IDS2Eval
py -3.12 -m venv venv
.\venv\Scripts\pip install -e ".[dev]"
```

Use `py -3.12` (the Python Launcher that every official python.org installer adds), not bare
`python`; see [Windows troubleshooting](#windows-troubleshooting) if more than one Python is on
your PATH.

## Extras

| Install | Adds |
|---|---|
| `pip install -e .` | the tool only |
| `pip install -e ".[plots]"` | `matplotlib`, needed for `output.write_scorecard_plot` |
| `pip install -e ".[dev]"` | `pytest` and `ruff`, for the test suite and lint |

The dependencies are listed in `pyproject.toml` only: `pyyaml`, `pandas`, `numpy`,
`scikit-learn`, `scipy`, `imbalanced-learn`, `xgboost` and `pyarrow`. All have prebuilt wheels
for Python 3.10 to 3.12 on Linux, macOS and Windows, so no compiler is needed.

## Commands

| | Linux / macOS | Windows |
|---|---|---|
| Dashboard | `venv/bin/ids2eval-dashboard` | `.\venv\Scripts\ids2eval-dashboard` |
| CLI | `venv/bin/ids2eval run --config my_config.yaml` | `.\venv\Scripts\ids2eval run --config my_config.yaml` |
| Tests | `venv/bin/pytest tests/ -v` | `.\venv\Scripts\pytest tests\ -v` |
| Lint | `venv/bin/ruff check ids2eval/ tests/` | `.\venv\Scripts\ruff check ids2eval/ tests/` |

The dashboard opens `http://localhost:8765` with a **New run** editor already filled in with
every config field and its default, so no YAML file is needed first. Tests and lint are what CI
runs on every push (`.github/workflows/ci.yml`, Linux only for now).

## Windows troubleshooting

- **More than one Python on PATH** (MSYS2/MinGW, the Microsoft Store placeholder, a per-user
  install) makes bare `python` run whichever one resolves first. Run `py --list` to see what is
  installed and use `py -3.12`, or another listed version from 3.10 to 3.12. A sign this already
  went wrong: `python -m venv venv` succeeds with no output, but `venv\Scripts` does not exist
  afterwards, because an MSYS2 Python creates a Unix-style `venv/bin` layout.
- **PowerShell needs the `.\` prefix** on every command above. Without it, PowerShell tries to
  resolve `venv\Scripts\pip` as a module name instead of a file path and fails with "module
  could not be loaded". `.\` works in `cmd.exe` too.
