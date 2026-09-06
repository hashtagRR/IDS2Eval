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
train/test splits. IDS<sup>2</sup>Eval runs 12 checks that catch these
problems automatically, instead of a one-off notebook redone by hand
for every paper, and rolls the result into a citable `SCORECARD.md` -
"this result was obtained on a dataset that passed the following
checks." See [AUDIT_CHECKS.md](AUDIT_CHECKS.md) for what each check
does and the scorecard's pass/fail rule.

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

```yaml
# my_config.yaml
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

See [INSTALL.md](INSTALL.md) for full setup, [USAGE.md](USAGE.md) for
the CLI/output files/programmatic API, and
[CONFIGURATION.md](CONFIGURATION.md) for how to customize a config
(field list: [`configs/schema.yaml`](configs/schema.yaml)).

## Documentation

| | |
|---|---|
| [INSTALL.md](INSTALL.md) | Setup, dependencies, verifying the install |
| [USAGE.md](USAGE.md) | CLI, output files, caching, reproducing a run, programmatic API |
| [CONFIGURATION.md](CONFIGURATION.md) | Config walkthrough with worked examples |
| [AUDIT_CHECKS.md](AUDIT_CHECKS.md) | What each of the 12 checks does, and the research behind it |
| [configs/schema.yaml](configs/schema.yaml) | Every field, one line each - copy it as your starting point |
| [examples/unsw-nb15-scorecard](examples/unsw-nb15-scorecard) | A real scorecard, chart included, run against the actual UNSW-NB15 dataset |

## Status

Implemented, tested (140 tests, CI on Python 3.10/3.11/3.12), and
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
[CONFIGURATION.md](CONFIGURATION.md#tuning-and-hyperparameters) for
why that matters.

`known_issue_lookup`'s two seed entries demonstrate the mechanism -
growing the curated table is a good area for contributors to help with
(see [AUDIT_CHECKS.md](AUDIT_CHECKS.md)).

## License

AGPL-3.0 - see [LICENSE](LICENSE).
