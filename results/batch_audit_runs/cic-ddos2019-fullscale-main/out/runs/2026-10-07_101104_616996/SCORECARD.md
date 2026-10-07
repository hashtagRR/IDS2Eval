# IDS2Eval Scorecard

**Dataset:** cic-ddos2019-fullscale
**Overall status:** 🚩 Review Required, 11 ok, 4 warning(s), 4 flag(s)
**Generated:** 2026-10-07T13:06:46.537339+00:00
**IDS2Eval version:** 0.1.0
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 2,184,498 (4.36%); test rows leaking a train feature-match: 244 (0.00%); test-internal duplicates: 650,949 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 83,443 feature vector(s) (200,263 rows, 0.28%) map to more than one label. The ground truth contradicts itself for these rows |
| 3 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 13 classes tested |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=15.4%, top2=24.2%)<br>*raw data:* no single feature or pair dominates importance (top1=15.4%, top2=24.0%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'Source Port <= 6.246e+04' reaches 0.0% test accuracy (39.1% train), vs. 0.0% from always predicting the majority class<br>*raw data:* single rule 'Source Port <= 6.245e+04' reaches 0.0% test accuracy (40.1% train), vs. 0.0% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'Total Length of Fwd Packets' alone reaches AUC 0.995 identifying 'Syn'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): Source IP: 1.0 (99.9%, 1.0), Destination IP: 0.889 (0.2%, 1.0), Source Port: 0.825 (100.0%, 0.825), Destination Port: 0.935 (100.0%, 0.935). Suggest dropping: ['Source IP', 'Destination IP', 'Source Port', 'Destination Port']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): Source IP: 1.0 (99.9%, 1.0), Destination IP: 0.889 (0.3%, 1.0), Source Port: 0.824 (100.0%, 0.824), Destination Port: 0.935 (100.0%, 0.935). Suggest dropping: ['Source IP', 'Destination IP', 'Source Port', 'Destination Port'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'Source Port' + 'Protocol' combined: 0.839. Port and protocol together may predict the label without attack behavior<br>*raw data:* standalone AUC of 'Source Port' + 'Protocol' combined: 0.841. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* adjacent-row label-transition rate (train=0.00, test=0.00) as a share of what a randomly shuffled ordering would produce; train is the most contiguous, consistent with rows still in collection order rather than shuffled before this split |
| 13 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 2 classes tested; for every class the 95% CI upper bound on (test-to-train minus train-internal) near-duplicate rate is below the +0.05 margin, so no class shows a train/test leakage signature |
| 14 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 15 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 13 classes, train imbalance ratio (majority:minority) = 41936:1; classes below 1% of train: ['UDP-lag', 'BENIGN', 'WebDDoS']<br>*raw data:* 13 classes, train imbalance ratio (majority:minority) = 45746:1; classes below 1% of train: ['UDP-lag', 'BENIGN', 'WebDDoS'] |
| 16 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'Source IP': 550, 'Destination IP': 598, 'Source Port': 61063, 'Destination Port': 65535} |
| 17 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* missing values in 1 feature column(s); +-inf values in 2 feature column(s); 12 constant/near-constant feature(s) |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* By design, the two collection days cover different attack sets: the testing day includes several DDoS types absent from the training day (e.g. DNS, NTP, SNMP, TFTP, WebDDoS reflection attacks), so a classifier trained only on the training day has never seen those attack types. (Sharafaldin et al. 2019, IEEE ICCST); The same attack type is labeled inconsistently between the two days (e.g. training's 'UDPLag'/'MSSQL' vs. testing's 'UDP-lag'/'DrDoS_MSSQL'), so label strings must be remapped before any train/test comparison, not matched literally. (Independently verified in this project's own audit methodology) |

## What cleaning removed

- Train: 50,063,112 → 47,878,614 rows (2,184,498 duplicates dropped)
- Test: 20,364,525 → 19,713,332 rows (244 train-leaking rows and 650,949 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 50,063,112 · test rows: 20,364,525 · features: 83
- Train content hash: `5899cb127b7cd6fe96b220054b775c9f78d2b89fcf2599f1841abe356e5a2b92`
- Test content hash: `29434b745e79629d042e8f0963a7f6c26bb97f89b6bcc503aedf6eba5786cbd3`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 11 ok, 4 warning(s), 4 flag(s) across 19 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
