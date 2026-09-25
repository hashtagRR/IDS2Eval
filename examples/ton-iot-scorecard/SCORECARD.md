# IDS2Eval Scorecard

**Dataset:** ton-iot
**Overall status:** ❌ Failed, 8 ok, 2 warning(s), 2 flag(s)
**Generated:** 2026-09-25T16:07:51.236670+00:00
**IDS2Eval version:** 0.1.0 (git 2ef764e)
**Scorecard schema version:** 1.1
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | ✅ pass | ✅ pass | train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | no feature vector maps to more than one label |
| 3 | `leakage_screen` | ✅ pass | ✅ pass | no single feature or pair dominates importance (top1=9.4%, top2=17.4%) |
| 4 | `one_rule_check` | ✅ pass | ✅ pass | single rule 'L4_DST_PORT <= 443.5' reaches 40.3% test accuracy (40.4% train) |
| 5 | `identity_column_flag` | 🚩 flag | 🚩 flag | standalone AUC by column: {'L4_DST_PORT': 0.896}. Suggest dropping: ['L4_DST_PORT'] |
| 6 | `temporal_leakage_check` | ✅ pass | ✅ pass | no schema.timestamp_column configured |
| 7 | `homogeneity_test` | 🚩 flag | 🚩 flag | 10 classes tested; leakage signature (test significantly closer than control, p<0.05) in: ['dos', 'backdoor'] |
| 8 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | 10 classes, train imbalance ratio (majority:minority) = 1177:1; classes below 1% of train: ['backdoor', 'mitm', 'ransomware'] |
| 9 | `low_cardinality_warning` | ✅ pass | ✅ pass | unique values by column: {'L4_DST_PORT': 49397} |
| 10 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | +-inf values in 2 feature column(s) |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | no known extractor signature matched |
| 2 | `known_issue_lookup` | ✅ pass | no curated known issues for dataset 'ton-iot' |

## What cleaning removed

- Train: 400,000 → 400,000 rows (0 duplicates dropped)
- Test: 100,000 → 100,000 rows (0 train-leaking rows and 0 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 400,000 · test rows: 100,000 · features: 41
- Train content hash: `03587bbee696fad295803a852004fc276e4ce227ac99539751cad0733c7034ef`
- Test content hash: `c737a0aff65db970152f95dff7e8f39d87f7b5a44bb4771146eef487884049f0`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.1), which reported failed, 8 ok, 2 warning(s), 2 flag(s) across 12 checks. Full report: audit_report_after.json.

Verdict rule: any flag → failed · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
