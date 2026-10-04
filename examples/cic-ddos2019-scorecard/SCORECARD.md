# IDS2Eval Scorecard

**Dataset:** cic-ddos2019
**Overall status:** 🚩 Review Required, 12 ok, 4 warning(s), 3 flag(s)
**Generated:** 2026-09-27T02:28:01.610408+00:00
**IDS2Eval version:** 0.1.0 (git bbbaa09)
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 4,083 (3.26%); test rows leaking a train feature-match: 6,763 (2.21%); test-internal duplicates: 2,409 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 5,623 feature vector(s) (13,758 rows, 3.19%) map to more than one label. The ground truth contradicts itself for these rows; 4,853 of these span train and test |
| 3 | `near_duplicate_class_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 98 of 3,447 sampled rows (2.84%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'NetBIOS / Portmap': 92, 'LDAP / MSSQL': 6}<br>*raw data:* 341 of 3,555 sampled rows (9.59%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'NetBIOS / Portmap': 316, 'LDAP / MSSQL': 9, 'MSSQL / Portmap': 5, 'UDP / UDPLag': 4, 'MSSQL / UDP': 4} |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=8.3%, top2=14.5%)<br>*raw data:* no single feature or pair dominates importance (top1=7.3%, top2=14.4%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'Avg Packet Size <= 7.625' reaches 11.5% test accuracy (68.1% train)<br>*raw data:* single rule 'Avg Packet Size <= 7.625' reaches 11.4% test accuracy (68.0% train) |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'Packet Length Min' alone reaches AUC 0.997 identifying 'LDAP'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 8 | `port_protocol_shortcut_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no port-like entry in schema.id_like_columns and/or no proto-like column found, this check needs both |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* adjacent-row label-transition rate (train=0.05, test=0.18) as a share of what a randomly shuffled ordering would produce; train is the most contiguous, consistent with rows still in collection order rather than shuffled before this split<br>*raw data:* adjacent-row label-transition rate (train=0.06, test=0.17) as a share of what a randomly shuffled ordering would produce; train is the most contiguous, consistent with rows still in collection order rather than shuffled before this split |
| 13 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 2 classes tested; test-to-train and train-internal proximity statistically indistinguishable for every class (consistent with inherent class homogeneity, not train/test leakage) |
| 14 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 15 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 8 classes, train imbalance ratio (majority:minority) = 1312:1; classes below 1% of train: ['NetBIOS', 'Portmap', 'UDPLag']<br>*raw data:* 8 classes, train imbalance ratio (majority:minority) = 888:1; classes below 1% of train: ['Portmap', 'NetBIOS', 'UDPLag'] |
| 16 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 17 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 12 constant/near-constant feature(s) |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* By design, the two collection days cover different attack sets: the testing day includes several DDoS types absent from the training day (e.g. DNS, NTP, SNMP, TFTP, WebDDoS reflection attacks), so a classifier trained only on the training day has never seen those attack types. (Sharafaldin et al. 2019, IEEE ICCST); The same attack type is labeled inconsistently between the two days (e.g. training's 'UDPLag'/'MSSQL' vs. testing's 'UDP-lag'/'DrDoS_MSSQL'), so label strings must be remapped before any train/test comparison, not matched literally. (Independently verified in this project's own audit methodology) |

## What cleaning removed

- Train: 125,170 → 121,087 rows (4,083 duplicates dropped)
- Test: 306,201 → 297,029 rows (6,763 train-leaking rows and 2,409 test-internal duplicates dropped)

## Compared to the previous run

Compared to `2026-09-25_153943_449369` (2026-09-25T15:40:39.405627+00:00).
No check's status changed since the previous run.

## Dataset fingerprint

- Train rows: 125,170 · test rows: 306,201 · features: 77
- Train content hash: `0d2aca1b3453d9b224be088b6e2000ab2181a32a14bd331d4349f1620148ec63`
- Test content hash: `71b75ac9db06a3be8a7d6d0479191e6c40af349a3a5fca22402baa55c95df308`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 12 ok, 4 warning(s), 3 flag(s) across 19 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
