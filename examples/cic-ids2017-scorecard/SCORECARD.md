# IDS2Eval Scorecard

**Dataset:** cic-ids2017
**Overall status:** 🚩 Review Required, 12 ok, 4 warning(s), 3 flag(s)
**Generated:** 2026-10-07T11:35:54.625003+00:00
**IDS2Eval version:** 0.1.0 (git be73293)
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

<img src="scorecard.png" alt="IDS2Eval Scorecard" width="760">

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 247,799 (10.94%); test rows leaking a train feature-match: 81,604 (14.41%); test-internal duplicates: 2,516 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 719 feature vector(s) (7,144 rows, 0.25%) map to more than one label. The ground truth contradicts itself for these rows; 335 of these span train and test |
| 3 | `near_duplicate_class_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 2 of 6,029 sampled rows (0.03%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'DoS Slowhttptest / DoS slowloris': 2} |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=6.7%, top2=12.7%)<br>*raw data:* no single feature or pair dominates importance (top1=6.4%, top2=11.3%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'Bwd Packet Length Std <= 1495' reaches 90.0% test accuracy (89.0% train), vs. 83.7% from always predicting the majority class<br>*raw data:* single rule 'Bwd Packet Length Std <= 1495' reaches 85.6% test accuracy (85.6% train), vs. 80.3% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'Bwd Packet Length Max' alone reaches AUC 1.000 identifying 'Heartbleed'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): Destination Port: 0.936 (99.4%, 0.935). Suggest dropping: ['Destination Port']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): Destination Port: 0.936 (99.5%, 0.936). Suggest dropping: ['Destination Port'] |
| 8 | `port_protocol_shortcut_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no port-like entry in schema.id_like_columns and/or no proto-like column found, this check needs both |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ⚠️ warn | ✅ pass | *Evidence: statistical.* 12 classes tested; for every class the 95% CI upper bound on (test-to-train minus train-internal) near-duplicate rate is below the +0.05 margin, so no class shows a train/test leakage signature<br>*raw data:* 12 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['FTP-Patator', 'SSH-Patator']; sample size isn't enough to tell for these classes |
| 14 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 15 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 15 classes, train imbalance ratio (majority:minority) = 185530:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'DoS slowloris', 'DoS Slowhttptest', 'SSH-Patator', 'Bot', 'Web Attack � Brute Force', 'Web Attack � XSS', 'Infiltration', 'Web Attack � Sql Injection', 'Heartbleed']<br>*raw data:* 15 classes, train imbalance ratio (majority:minority) = 202053:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'SSH-Patator', 'DoS slowloris', 'DoS Slowhttptest', 'Bot', 'Web Attack � Brute Force', 'Web Attack � XSS', 'Infiltration', 'Web Attack � Sql Injection', 'Heartbleed'] |
| 16 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'Destination Port': 51291} |
| 17 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* missing values in 1 feature column(s); +-inf values in 2 feature column(s); 8 constant/near-constant feature(s) |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The traffic capture has packet misorder and duplication, and some attacks that were actually launched are not correctly labeled as attack traffic in the released CSVs. (Engelen et al. 2021, IEEE S&P Workshops (WTMC)); A full re-labeling of the original release found 6.67% of labels wrong, with the error rate above 75% for some attack classes. (Liu et al. 2022, IEEE CNS (rates as summarized by Cantone et al. 2024)); Heartbleed has only 11 rows (about 0.0004% of the dataset), too few to evaluate reliably regardless of labeling accuracy. (Cantone et al. 2024, IEEE Access, Table 1) |

## What cleaning removed

- Train: 2,264,594 → 2,016,795 rows (247,799 duplicates dropped)
- Test: 566,149 → 482,029 rows (81,604 train-leaking rows and 2,516 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 2,264,594 · test rows: 566,149 · features: 78
- Train content hash: `5864fd3ca0c2d57589584902c07a712bd806130c638ac6d48626969975b9a362`
- Test content hash: `722dafecb77262e4a8661066ff0cd478cf1574faa31ebb8bfc987d5ae3673eea`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 12 ok, 4 warning(s), 3 flag(s) across 19 checks. Full report: audit_report_after.json. A vector figure of this chart is at `scorecard.pdf`, ready to cite directly.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
