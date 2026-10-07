# IDS2Eval Scorecard

**Dataset:** cic-ids2017-glf
**Overall status:** 🚩 Review Required, 15 ok, 4 warning(s), 3 flag(s)
**Generated:** 2026-10-07T14:29:46.198000+00:00
**IDS2Eval version:** 0.1.0
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 9,191 (0.41%); test rows leaking a train feature-match: 3,825 (0.68%); test-internal duplicates: 319 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 13 classes tested |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=15.1%, top2=21.7%)<br>*raw data:* no single feature or pair dominates importance (top1=17.2%, top2=31.0%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'Source IP <= 1.5' reaches 83.1% test accuracy (83.3% train), vs. 80.6% from always predicting the majority class<br>*raw data:* single rule 'Source IP <= 0.5' reaches 88.3% test accuracy (88.3% train), vs. 80.3% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'Bwd Packet Length Max' alone reaches AUC 1.000 identifying 'Heartbleed'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): Source IP: 0.985 (99.9%, 0.985), Destination IP: 0.98 (99.9%, 0.98), Source Port: 0.843 (100.0%, 0.843), Destination Port: 0.936 (99.5%, 0.936). Suggest dropping: ['Source IP', 'Destination IP', 'Source Port', 'Destination Port']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): Source IP: 0.985 (99.9%, 0.985), Destination IP: 0.98 (99.9%, 0.98), Source Port: 0.845 (100.0%, 0.845), Destination Port: 0.936 (99.5%, 0.936). Suggest dropping: ['Source IP', 'Destination IP', 'Source Port', 'Destination Port'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'Source Port' + 'Protocol' combined: 0.907. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 12 classes tested; for every class the 95% CI upper bound on (test-to-train minus train-internal) near-duplicate rate is below the +0.05 margin, so no class shows a train/test leakage signature |
| 14 | `resplit_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9995, grouped-split accuracy=0.9994 (drop=+0.0000); grouped split reproduces random-split accuracy, consistent with inherent class homogeneity rather than a split-artifact explanation |
| 15 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 16 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 15 classes, train imbalance ratio (majority:minority) = 201575:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'SSH-Patator', 'DoS slowloris', 'DoS Slowhttptest', 'Bot', 'Web Attack – Brute Force', 'Web Attack – XSS', 'Infiltration', 'Web Attack – Sql Injection', 'Heartbleed']<br>*raw data:* 15 classes, train imbalance ratio (majority:minority) = 202053:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'SSH-Patator', 'DoS slowloris', 'DoS Slowhttptest', 'Bot', 'Web Attack – Brute Force', 'Web Attack – XSS', 'Infiltration', 'Web Attack – Sql Injection', 'Heartbleed'] |
| 17 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'Source IP': 16328, 'Destination IP': 18766, 'Source Port': 64558, 'Destination Port': 51291} |
| 18 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* missing values in 1 feature column(s); +-inf values in 2 feature column(s); 8 constant/near-constant feature(s) |
| 19 | `result_robustness_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.9976 (identity_columns_dropped) to 0.9995 (deduplicated) across 4 conditions, a spread of 0.0019 (sampling margin +/-0.0001) |
| 20 | `repeated_seed_falsification_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* grouped-split accuracy drop across 10 seeds: mean=+0.0000, 95% CI=[-0.0000, +0.0001]; not material: even the most generous estimate in the 95% CI (+0.0001) stays below the +0.0100 materiality threshold |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The traffic capture has packet misorder and duplication, and some attacks that were actually launched are not correctly labeled as attack traffic in the released CSVs. (Engelen et al. 2021, IEEE S&P Workshops (WTMC)); A full re-labeling of the original release found 6.67% of labels wrong, with the error rate above 75% for some attack classes. (Liu et al. 2022, IEEE CNS (rates as summarized by Cantone et al. 2024)); Heartbleed has only 11 rows (about 0.0004% of the dataset), too few to evaluate reliably regardless of labeling accuracy. (Cantone et al. 2024, IEEE Access, Table 1) |

## What cleaning removed

- Train: 2,264,594 → 2,255,403 rows (9,191 duplicates dropped)
- Test: 566,149 → 562,005 rows (3,825 train-leaking rows and 319 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 2,264,594 · test rows: 566,149 · features: 82
- Train content hash: `c502fed3ca3edcce9767e01f95b3788905b75aadc83c7eb39bd587c4c7b49327`
- Test content hash: `50a9575ddae1b0c876ab7794bbbd42547cec3bd674927620e0d417de1ebf1ae8`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 15 ok, 4 warning(s), 3 flag(s) across 22 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
