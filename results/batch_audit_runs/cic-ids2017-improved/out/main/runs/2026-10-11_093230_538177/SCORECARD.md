# IDS2Eval Scorecard

**Dataset:** cic-ids2017-improved
**Overall status:** 🚩 Review Required, 11 ok, 4 warning(s), 3 flag(s), 4 not applicable
**Generated:** 2026-10-11T10:02:32.908938+00:00
**IDS2Eval version:** 0.2.1
**Scorecard schema version:** 1.4
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 7,417 (0.44%); test rows leaking a train feature-match: 2,718 (0.65%); test-internal duplicates: 179 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 22 classes tested |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=6.2%, top2=10.8%)<br>*raw data:* no single feature or pair dominates importance (top1=5.7%, top2=11.3%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'RST Flag Count <= 0.5' reaches 76.1% test accuracy (76.1% train), vs. 75.5% from always predicting the majority class<br>*raw data:* single rule 'RST Flag Count <= 0.5' reaches 76.0% test accuracy (76.1% train), vs. 75.4% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'Bwd Packet Length Max' alone reaches AUC 1.000 identifying 'Heartbleed'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): Src IP: 0.976 (100.0%, 0.976), Dst IP: 0.98 (99.8%, 0.98), Src Port: 0.824 (99.9%, 0.824), Dst Port: 0.963 (99.8%, 0.963). Suggest dropping: ['Src IP', 'Dst IP', 'Src Port', 'Dst Port']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): Src IP: 0.976 (100.0%, 0.976), Dst IP: 0.98 (99.8%, 0.98), Src Port: 0.827 (99.9%, 0.827), Dst Port: 0.963 (99.8%, 0.963). Suggest dropping: ['Src IP', 'Dst IP', 'Src Port', 'Dst Port'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'Src Port' + 'Protocol' combined: 0.903. Port and protocol together may predict the label without attack behavior<br>*raw data:* standalone AUC of 'Src Port' + 'Protocol' combined: 0.904. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 17 classes tested; for every class the 95% CI upper bound on (test-to-train minus train-internal) near-duplicate rate is below the +0.05 margin, so no class shows a train/test leakage signature |
| 14 | `resplit_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9994, grouped-split accuracy=0.9996 (drop=-0.0002); grouped split reproduces random-split accuracy: no evidence that information tied to the grouping key drives the result (other grouping keys and shortcuts are not tested) |
| 15 | `scenario_holdout_falsification` | ⚪ n/a (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 16 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 27 classes, train imbalance ratio (majority:minority) = 315172:1; classes below 1% of train: ['DoS GoldenEye', 'Botnet - Attempted', 'FTP-Patator', 'DoS Slowloris', 'DoS Slowhttptest - Attempted', 'SSH-Patator', 'DoS Slowloris - Attempted', 'DoS Slowhttptest', 'Web Attack - Brute Force - Attempted', 'Botnet', 'Web Attack - XSS - Attempted', 'DoS Hulk - Attempted', 'DoS GoldenEye - Attempted', 'Web Attack - Brute Force', 'Infiltration - Attempted', 'Infiltration', 'SSH-Patator - Attempted', 'Web Attack - XSS', 'FTP-Patator - Attempted', 'Web Attack - SQL Injection', 'Heartbleed', 'Web Attack - SQL Injection - Attempted']<br>*raw data:* 27 classes, train imbalance ratio (majority:minority) = 316513:1; classes below 1% of train: ['DoS GoldenEye', 'Botnet - Attempted', 'FTP-Patator', 'DoS Slowloris', 'DoS Slowhttptest - Attempted', 'SSH-Patator', 'DoS Slowloris - Attempted', 'DoS Slowhttptest', 'Web Attack - Brute Force - Attempted', 'Botnet', 'Web Attack - XSS - Attempted', 'DoS Hulk - Attempted', 'DoS GoldenEye - Attempted', 'Web Attack - Brute Force', 'Infiltration - Attempted', 'Infiltration', 'SSH-Patator - Attempted', 'Web Attack - XSS', 'FTP-Patator - Attempted', 'Web Attack - SQL Injection', 'Heartbleed', 'Web Attack - SQL Injection - Attempted'] |
| 17 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'Src IP': 152, 'Dst IP': 18508, 'Src Port': 64503, 'Dst Port': 4370} |
| 18 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* +-inf values in 2 feature column(s); 1 constant/near-constant feature(s) |
| 19 | `result_robustness_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.9940 (identity_columns_dropped) to 0.9996 (grouped_split) across 4 conditions, a spread of 0.0056 (sampling margin +/-0.0002) |
| 20 | `repeated_seed_falsification_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* grouped-split accuracy drop across 10 seeds: mean=-0.0000, 95% CI=[-0.0001, +0.0001]; not material: even the most generous estimate in the 95% CI (+0.0001) stays below the +0.0100 materiality threshold |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The traffic capture has packet misorder and duplication, and some attacks that were actually launched are not correctly labeled as attack traffic in the released CSVs. (Engelen et al. 2021, IEEE S&P Workshops (WTMC)); A full re-labeling of the original release found 6.67% of labels wrong, with the error rate above 75% for some attack classes. (Liu et al. 2022, IEEE CNS (rates as summarized by Cantone et al. 2024)); Heartbleed has only 11 rows (about 0.0004% of the dataset), too few to evaluate reliably regardless of labeling accuracy. (Cantone et al. 2024, IEEE Access, Table 1) |

## Not run

Disabled in this run's config, so they produced no result and say nothing about the dataset. Checks marked n/a above ran but had no input to test. `synthetic_realism_check`, `cross_dataset_drift_check`, `cross_capture_matrix_check`, `feature_category_ablation_check`, `artifact_sensitivity_check`, `seed_sensitivity_check`.

## What cleaning removed

- Train: 1,679,980 → 1,672,563 rows (7,417 duplicates dropped)
- Test: 419,996 → 417,099 rows (2,718 train-leaking rows and 179 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 1,679,980 · test rows: 419,996 · features: 84
- Train content hash: `3d5a3784b3fc391852d5faf0e4f7dbcd3acb33a372b529fecefb394b6ec3a1b3`
- Test content hash: `7a9f88ee42a813489c38963aab8d40e37dc69e850b10f0e72703943935fbafc0`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.2.1 (scorecard schema 1.4), which reported review required, 11 ok, 4 warning(s), 3 flag(s), 4 not applicable across 22 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed; not applicable checks never change the verdict.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
