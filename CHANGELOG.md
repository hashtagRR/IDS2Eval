# Changelog

## Unreleased

- IDS<sup>2</sup>Eval is on PyPI: `pip install ids2eval`. The README and the install guide use it; installing from the source code is described separately.
- Python 3.13 is supported and tested in CI.
- Package metadata: SPDX license expression, project links and classifiers.
- Releases run from GitHub Actions (`.github/workflows/release.yml`): tests, version and changelog, PyPI upload with Trusted Publishing, and the GitHub release that Zenodo archives. See CONTRIBUTING.md.

No check, statistic or threshold changed.

## 0.2.1 (2026-10-11)

DOI [10.5281/zenodo.23301210](https://doi.org/10.5281/zenodo.23301210).

- A check with no input to test reports `not_applicable` instead of `ok`.
- An audit in which no check produced a result is `not_evaluated` instead of passed.
- Scorecards list the checks a config left disabled (schema 1.4).
- Known-issue warnings name the release they document.
- Adds the validation scripts and results of the paper's revision: host-disjoint splits, workflow ablation, interval coverage, class-adjusted reuse, and a comparison with Flood et al.'s released heuristics.

No statistic or threshold changed.

## 0.2.0 (2026-10-07)

DOI [10.5281/zenodo.23217301](https://doi.org/10.5281/zenodo.23217301).

The code, configurations and results behind the accompanying paper on auditing NIDS benchmarks.
