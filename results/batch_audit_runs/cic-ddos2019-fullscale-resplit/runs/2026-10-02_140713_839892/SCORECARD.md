# IDS2Eval Scorecard

**Dataset:** cic-ddos2019-fullscale-resplit
**Overall status:** ❌ Failed, 3 ok, 0 warning(s), 1 flag(s)
**Generated:** 2026-10-03T07:42:42.705238+00:00
**IDS2Eval version:** 0.1.0
**Scorecard schema version:** 1.2
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `resplit_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.8948, grouped-split accuracy=0.8947 (drop=+0.0001); grouped split reproduces random-split accuracy, consistent with inherent class homogeneity rather than a split-artifact explanation |
| 2 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 3 | `result_robustness_check` | 🚩 flag (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.7319 (identity_columns_dropped) to 0.8948 (random_split) across 4 conditions, a spread of 0.1628; the headline result depends on methodology choices as much as the classifier |
| 4 | `repeated_seed_falsification_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* grouped-split accuracy drop across 5 seeds: mean=-0.0001, 95% CI=[-0.0004, +0.0002]; not material: even the most generous estimate in the 95% CI (+0.0002) stays below the +0.0100 materiality threshold |

## Dataset fingerprint

- Train rows: 56,342,109 · test rows: 14,085,528 · features: 83
- Train content hash: `aab4bff8725d0f144519192a89a39702f6b4d587c6030aeb29c726ca33b5f190`
- Test content hash: `1d62938665c9bc456c99794a18be65645c4aa4e0afa3d698361782436c5f073e`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.2), which reported failed, 3 ok, 0 warning(s), 1 flag(s) across 4 checks. Full report: audit_report_after.json.

Verdict rule: any flag → failed · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
