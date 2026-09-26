# IDS2Eval Scorecard

**Dataset:** bot-iot
**Overall status:** ⚠️ Passed with warnings, 11 ok, 2 warning(s), 0 flag(s)
**Generated:** 2026-09-26T09:43:54.729365+00:00
**IDS2Eval version:** 0.1.0 (git 8cff297)
**Scorecard schema version:** 1.2
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | ✅ pass | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=12.2%, top2=22.1%) |
| 4 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'LONGEST_FLOW_PKT <= 34' reaches 90.8% test accuracy (90.8% train) |
| 5 | `identity_column_flag` | ✅ pass | ✅ pass | *Evidence: statistical.* standalone AUC by column: {'L4_DST_PORT': 0.531} |
| 6 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 7 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 4 classes tested; test-to-train and train-internal proximity statistically indistinguishable for every class (consistent with inherent class homogeneity, not train/test leakage) |
| 8 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 5 classes, train imbalance ratio (majority:minority) = 5065:1; classes below 1% of train: ['Benign', 'Theft'] |
| 9 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'L4_DST_PORT': 14608} |
| 10 | `data_integrity_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no missing labels, constant features, or +-inf values found |
| 11 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 5 classes tested |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The full dataset is over 99.9% attack traffic (benign flows are 129,437 of 30,420,086 rows, 0.43%), an order of magnitude more skewed than most NIDS datasets; a uniform row-level sample may carry very few or zero benign rows, and a classifier's accuracy on this data mostly reflects its attack-vs-attack discrimination, not its ability to recognize normal traffic. (Koroniotis et al. 2019, Future Generation Computer Systems) |

## What cleaning removed

- Train: 400,000 → 400,000 rows (0 duplicates dropped)
- Test: 100,000 → 100,000 rows (0 train-leaking rows and 0 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 400,000 · test rows: 100,000 · features: 41
- Train content hash: `195acbd1258af37d422916d1c46863eb7c8267976b1196fdfc39f187b7f05d1e`
- Test content hash: `df600d41362e37f20cf37a9857a716a8b31c531ccf4084faf2e7e3744ac80ef0`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.2), which reported passed with warnings, 11 ok, 2 warning(s), 0 flag(s) across 13 checks. Full report: audit_report_after.json.

Verdict rule: any flag → failed · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
