# IDS<sup>2</sup>Eval

**[hashtagRR.github.io/IDS2Eval](https://hashtagRR.github.io/IDS2Eval)**

[![PyPI](https://img.shields.io/pypi/v/ids2eval?label=PyPI)](https://pypi.org/project/ids2eval/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23217300.svg)](https://doi.org/10.5281/zenodo.23217300)

<p align="center">
  <img src="https://raw.githubusercontent.com/hashtagRR/IDS2Eval/main/docs/img/ids2eval-overview.svg" width="100%"
       alt="IDS2Eval overview: a NIDS dataset and a YAML config go through four kinds of check (diagnose, 18 checks; control, 1; intervene, 8; look up known issues, 1), run on the raw data and again after removing duplicates, and every verdict lands in one scorecard. ids2eval recommend suggests config fixes for flagged checks.">
</p>

A config-driven toolkit that audits network intrusion detection (NIDS)
datasets before you trust a result on them. It runs 28 checks for
duplicated rows, label conflicts, one-column shortcuts and split
problems, tests whether a suspected problem actually changes the
accuracy, and records every verdict in a citable scorecard.

*IDS<sup>2</sup> reads both ways: **I**ntrusion **D**etection **S**ystems and
**I**ntrusion **D**ata **S**ets.*

## Quickstart

```bash
python3 -m venv venv && venv/bin/pip install "ids2eval[plots]"
venv/bin/ids2eval-dashboard                      # web UI with a pre-filled config editor
venv/bin/ids2eval run --config my_config.yaml    # or the CLI, with a config like the one below
```

```yaml
# my_config.yaml: any NIDS dataset in CSV or Parquet form
dataset:
  name: my-dataset
  raw_files: ["data.csv"]
schema:
  label_column: Label
```

Windows, installing from the source code, and troubleshooting: [INSTALL.md](https://github.com/hashtagRR/IDS2Eval/blob/main/INSTALL.md).

## Documentation

| Guide | What it covers |
|---|---|
| [Usage](https://github.com/hashtagRR/IDS2Eval/blob/main/guide/usage.md) | the CLI, the dashboard, output files, caching, reproducing a run, and the Python API |
| [Config fields](https://github.com/hashtagRR/IDS2Eval/blob/main/configs/README.md) | every config field, with its default and an example |
| [Configuration notes](https://github.com/hashtagRR/IDS2Eval/blob/main/guide/configuration.md) | the reasoning behind non-obvious fields, and larger worked examples |
| [Checks](https://github.com/hashtagRR/IDS2Eval/blob/main/guide/checks.md) | what each of the 28 checks does, the research behind it, and the scorecard's verdict rule |
| [Example scorecards](https://github.com/hashtagRR/IDS2Eval/blob/main/examples/README.md) | the real audit runs behind the paper, on seven widely used NIDS benchmarks |
| [Paper results](https://github.com/hashtagRR/IDS2Eval/blob/main/results/README.md) | configurations, scorecards and analysis outputs behind the accompanying paper |
| [Known issues](https://github.com/hashtagRR/IDS2Eval/blob/main/guide/contributing-known-issues.md) | how to add a curated known issue or extractor fingerprint |
| [Install guide](https://github.com/hashtagRR/IDS2Eval/blob/main/INSTALL.md) | platform setup, extras, tests and lint, including Windows |
| [Contributing](https://github.com/hashtagRR/IDS2Eval/blob/main/CONTRIBUTING.md) | development setup and how releases are made |
| [Project site](https://hashtagRR.github.io/IDS2Eval) | the project's overview page |

## Versions

Every release and its changes are in the [changelog](https://github.com/hashtagRR/IDS2Eval/blob/main/CHANGELOG.md); each one is archived on Zenodo under the concept DOI above.

- **`v0.2.1`** ([10.5281/zenodo.23301210](https://doi.org/10.5281/zenodo.23301210)): a check with no input to test reports `not_applicable` instead of `ok`, an audit in which no check produced a result is `not_evaluated` instead of passed, scorecards list the checks a config left disabled (schema 1.4), and known-issue warnings name the release they document; no statistic or threshold changed. Also adds the validation scripts and results of the paper's revision (host-disjoint splits, workflow ablation, interval coverage, class-adjusted reuse, a comparison with Flood et al.'s released heuristics).
- **`v0.2.0`** ([10.5281/zenodo.23217301](https://doi.org/10.5281/zenodo.23217301)): the code, configurations and results behind the accompanying paper on auditing NIDS benchmarks (in preparation).

IDS<sup>2</sup>Eval grew out of the dataset-auditing code of research on
machine-learning-based network intrusion detection, generalized into a
dataset-independent toolkit.

## Citing

Cite the version you used. The concept DOI
[10.5281/zenodo.23217300](https://doi.org/10.5281/zenodo.23217300)
always resolves to the latest version.

> Relapanawa, R. (2026). *IDS2Eval 0.2.1* (Version v0.2.1) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.23301210

The results, configurations and analysis scripts behind the accompanying paper are archived separately:

> Relapanawa, R. (2026). *IDS2Eval paper: research artifacts (results, configurations and analysis scripts)* [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.23301258

## License

AGPL-3.0. See [LICENSE](https://github.com/hashtagRR/IDS2Eval/blob/main/LICENSE).
