# IDS<sup>2</sup>Eval

**[hashtagRR.github.io/IDS2Eval](https://hashtagRR.github.io/IDS2Eval)**

*IDS<sup>2</sup> — the name works both ways: **I**ntrusion **D**etection
**S**ystems, and **I**ntrusion **D**ata **S**ets. (GitHub repo names
can't do superscripts, hence `IDS2Eval`.)*

A config-driven data-quality-audit and benchmarking toolkit for
network intrusion detection (NIDS) datasets.

Most published NIDS results are evaluated on benchmark datasets
(UNSW-NB15, CIC-IDS2018, and others) whose quality is largely taken on
faith. IDS<sup>2</sup>Eval operationalizes a systematic audit methodology —
feature-importance-driven leakage screening, a nearest-neighbor
class-homogeneity test, a resplit falsification test, and 9 more — as
reusable, config-driven software, rather than a one-off analysis
notebook per dataset. See [AUDIT_CHECKS.md](AUDIT_CHECKS.md) for what
each of the 12 checks actually does and the published findings behind
them.

Unlike general-purpose AutoML tools (PyCaret, AutoGluon, TPOT),
IDS<sup>2</sup>Eval's focus is IDS-specific, already-validated data-quality
checks rather than breadth of ML algorithms — feature engineering
(imputation, feature selection, dimensionality reduction) is
deliberately out of scope for the same reason.

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
[CONFIGURATION.md](CONFIGURATION.md) for the config surface
(exhaustive field reference: [`configs/schema.yaml`](configs/schema.yaml)).

## Documentation

| | |
|---|---|
| [INSTALL.md](INSTALL.md) | Setup, dependencies, verifying the install |
| [USAGE.md](USAGE.md) | CLI, output files, caching, reproducing a run, programmatic API |
| [CONFIGURATION.md](CONFIGURATION.md) | Config walkthrough with worked examples |
| [AUDIT_CHECKS.md](AUDIT_CHECKS.md) | What each of the 12 checks does, and the research behind it |
| [configs/schema.yaml](configs/schema.yaml) | Exhaustive, commented field-by-field reference |

## Status

Implemented, tested (121 tests, CI on Python 3.10/3.11/3.12), and
validated against real data — not just synthetic fixtures:

- **UNSW-NB15** (full dataset) — audit + 5 classifiers, including
  `tuning: true` with a multi-strategy sampling comparison, ran
  cleanly end to end. Feature importance independently reproduced the
  published `sttl` TTL-topology bias; the before/after-dedup audit
  surfaced a real finding (class balance shifted from 2:1 to roughly
  1:1 after removing duplicates — they were disproportionately one
  class)
- **CIC-IDS2018** (official 10-file, 16.2M-row distribution) —
  chunked loading + reservoir sampling kept peak memory at 3.0GB on a
  7.8GB-RAM machine; `identity_column_flag` independently reproduced
  the published `Dst Port` leakage finding

**Correctness note — scaling/sampling and cross-validation.** Both run
inside the same `imblearn` pipeline as the classifier, not once up
front, so `classifiers.tuning`'s internal CV folds and
`classifiers.calibration`'s internal folds each redo scaling/sampling
independently. Fitting a scaler or a sampler like SMOTE once on the
whole training set and only then handing the result to
`GridSearchCV`/`CalibratedClassifierCV` lets their internal folds see
data transformed using information from other, supposedly-held-out
folds — SMOTE's synthetic points are the sharpest version of this,
since a fold's synthetic rows can be interpolated from real neighbors
that landed in a different fold.

Not yet implemented: a `known_issue_lookup` table beyond its current
two seed entries (open-ended curation, see
[AUDIT_CHECKS.md](AUDIT_CHECKS.md)), and automatic comparison across
*scaling* strategies the way sampling already supports (see
[CONFIGURATION.md](CONFIGURATION.md)).

## License

AGPL-3.0 — see [LICENSE](LICENSE).
