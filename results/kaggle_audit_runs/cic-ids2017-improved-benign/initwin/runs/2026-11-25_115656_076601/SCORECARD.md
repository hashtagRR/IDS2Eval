# IDS2Eval Scorecard

**Dataset:** cic-ids2017-improved-initwin
**Overall status:** 🚩 Review Required, 9 ok, 5 warning(s), 3 flag(s), 4 not applicable
**Generated:** 2026-11-25T12:36:24.377345+00:00
**IDS2Eval version:** 0.2.3
**Scorecard schema version:** 1.4
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 7,332 (0.44%); test rows leaking a train feature-match: 2,799 (0.67%); test-internal duplicates: 183 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 13 classes tested |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=5.7%, top2=10.9%)<br>*raw data:* no single feature or pair dominates importance (top1=6.2%, top2=11.7%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'Src IP <= 1.5' reaches 78.5% test accuracy (78.4% train), vs. 76.0% from always predicting the majority class<br>*raw data:* single rule 'RST Flag Count <= 0.5' reaches 76.4% test accuracy (76.5% train), vs. 75.9% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'Bwd Packet Length Max' alone reaches AUC 1.000 identifying 'Heartbleed'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): Src IP: 0.976 (100.0%, 0.976), Dst IP: 0.978 (99.8%, 0.978), Src Port: 0.824 (99.9%, 0.825), Dst Port: 0.962 (99.8%, 0.962). Suggest dropping: ['Src IP', 'Dst IP', 'Src Port', 'Dst Port']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): Src IP: 0.976 (100.0%, 0.976), Dst IP: 0.978 (99.8%, 0.978), Src Port: 0.827 (99.9%, 0.828), Dst Port: 0.963 (99.8%, 0.962). Suggest dropping: ['Src IP', 'Dst IP', 'Src Port', 'Dst Port'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'Src Port' + 'Protocol' combined: 0.904. Port and protocol together may predict the label without attack behavior<br>*raw data:* standalone AUC of 'Src Port' + 'Protocol' combined: 0.905. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 11 classes tested; for every class the 95% CI upper bound on (test-to-train minus train-internal) near-duplicate rate is below the +0.05 margin, so no class shows excess cross-boundary matching |
| 14 | `resplit_falsification` | ⚠️ warn (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9998, grouped-split accuracy=0.9998 (drop=+0.0000); balanced accuracy drop=+0.0640, macro-F1 drop=+0.0670 (accuracy not material, balanced accuracy inconclusive, macro f1 inconclusive); grouping key: 1,084,821 groups over 2,099,976 rows (1.94 rows per group, 40.7% of rows in single-row groups); inconclusive: a drop exceeds its threshold only within its sampling margin at this test size, see repeated_seed_falsification_check |
| 15 | `scenario_holdout_falsification` | ⚪ n/a (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 16 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 16 classes, train imbalance ratio (majority:minority) = 141148:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'DoS Slowloris', 'SSH-Patator', 'DoS Slowhttptest', 'Botnet', 'Web Attack - Brute Force', 'Infiltration', 'Web Attack - XSS', 'Web Attack - SQL Injection', 'Heartbleed']<br>*raw data:* 16 classes, train imbalance ratio (majority:minority) = 141737:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'DoS Slowloris', 'SSH-Patator', 'DoS Slowhttptest', 'Botnet', 'Web Attack - Brute Force', 'Infiltration', 'Web Attack - XSS', 'Web Attack - SQL Injection', 'Heartbleed'] |
| 17 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'Src IP': 146, 'Dst IP': 18519, 'Src Port': 64497, 'Dst Port': 4372} |
| 18 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* +-inf values in 2 feature column(s) |
| 19 | `result_robustness_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.9947 (identity_columns_dropped) to 0.9998 (deduplicated) across 4 conditions, a spread of 0.0051 (sampling margin +/-0.0002); balanced accuracy spread 0.0640, macro-F1 spread 0.0670; accuracy not material, balanced accuracy not material, macro f1 not material |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The traffic capture has packet misorder and duplication, and some attacks that were actually launched are not correctly labeled as attack traffic in the released CSVs. (applies to the original CIC-IDS2017 CSVs (UNB); Engelen et al. 2021, IEEE S&P Workshops (WTMC)); A full re-labeling of the original release found 6.67% of labels wrong, with the error rate above 75% for some attack classes. (applies to the original CIC-IDS2017 CSVs (UNB); Liu et al. 2022, IEEE CNS (rates as summarized by Cantone et al. 2024)); Heartbleed has only 11 rows (about 0.0004% of the dataset), too few to evaluate reliably regardless of labeling accuracy. (applies to the original CIC-IDS2017 CSVs and the corrected re-extraction alike; Cantone et al. 2024, IEEE Access, Table 1) |

## Not run

Disabled in this run's config, so they produced no result and say nothing about the dataset. Checks marked n/a above ran but had no input to test. `synthetic_realism_check`, `cross_dataset_drift_check`, `cross_capture_matrix_check`, `feature_category_ablation_check`, `artifact_sensitivity_check`, `seed_sensitivity_check`, `reuse_removal_falsification`, `repeated_seed_falsification_check`.

## What cleaning removed

- Train: 1,679,980 → 1,672,648 rows (7,332 duplicates dropped)
- Test: 419,996 → 417,014 rows (2,799 train-leaking rows and 183 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 1,679,980 · test rows: 419,996 · features: 86
- Train content hash: `141bcf2b8ed5737b9d5891cdfc08f78d4a2ad9c0ecb1fb3337b55d390a787752`
- Test content hash: `077dc214f7acd348de41abee5291ef2e25c61981fe9a2d40ee3764f162f26269`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.2.3 (scorecard schema 1.4), which reported review required, 9 ok, 5 warning(s), 3 flag(s), 4 not applicable across 21 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed; not applicable checks never change the verdict; if no check produced a result → not evaluated.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
