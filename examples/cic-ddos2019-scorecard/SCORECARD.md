# IDS2Eval Scorecard

**Dataset:** cic-ddos2019
**Overall status:** ❌ Failed, 8 ok, 4 warning(s), 1 flag(s)
**Generated:** 2026-09-26T08:53:58.123213+00:00
**IDS2Eval version:** 0.1.0 (git 8cff297)
**Scorecard schema version:** 1.2
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 4,083 (3.26%); test rows leaking a train feature-match: 6,763 (2.21%); test-internal duplicates: 2,409 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 5,623 feature vector(s) (13,758 rows, 3.19%) map to more than one label. The ground truth contradicts itself for these rows; 4,853 of these span train and test |
| 3 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=8.3%, top2=14.5%)<br>*raw data:* no single feature or pair dominates importance (top1=7.3%, top2=14.4%) |
| 4 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'Avg Packet Size <= 7.625' reaches 11.5% test accuracy (68.1% train)<br>*raw data:* single rule 'Avg Packet Size <= 7.625' reaches 11.4% test accuracy (68.0% train) |
| 5 | `identity_column_flag` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 6 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 7 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 2 classes tested; test-to-train and train-internal proximity statistically indistinguishable for every class (consistent with inherent class homogeneity, not train/test leakage) |
| 8 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 8 classes, train imbalance ratio (majority:minority) = 1312:1; classes below 1% of train: ['NetBIOS', 'Portmap', 'UDPLag']<br>*raw data:* 8 classes, train imbalance ratio (majority:minority) = 888:1; classes below 1% of train: ['Portmap', 'NetBIOS', 'UDPLag'] |
| 9 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 10 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 12 constant/near-constant feature(s) |
| 11 | `near_duplicate_class_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 98 of 3,447 sampled rows (2.84%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'NetBIOS / Portmap': 92, 'LDAP / MSSQL': 6}<br>*raw data:* 341 of 3,555 sampled rows (9.59%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'NetBIOS / Portmap': 316, 'LDAP / MSSQL': 9, 'MSSQL / Portmap': 5, 'UDP / UDPLag': 4, 'MSSQL / UDP': 4} |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ⚠️ warn | *Evidence: documented.* matched extractor signature(s): ['CICFlowMeter'] |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* By design, the two collection days cover different attack sets: the testing day includes several DDoS types absent from the training day (e.g. DNS, NTP, SNMP, TFTP, WebDDoS reflection attacks), so a classifier trained only on the training day has never seen those attack types. (Sharafaldin et al. 2019, IEEE ICCST); The same attack type is labeled inconsistently between the two days (e.g. training's 'UDPLag'/'MSSQL' vs. testing's 'UDP-lag'/'DrDoS_MSSQL'), so label strings must be remapped before any train/test comparison, not matched literally. (Independently verified in this project's own audit methodology) |

## What cleaning removed

- Train: 125,170 → 121,087 rows (4,083 duplicates dropped)
- Test: 306,201 → 297,029 rows (6,763 train-leaking rows and 2,409 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 125,170 · test rows: 306,201 · features: 77
- Train content hash: `0d2aca1b3453d9b224be088b6e2000ab2181a32a14bd331d4349f1620148ec63`
- Test content hash: `71b75ac9db06a3be8a7d6d0479191e6c40af349a3a5fca22402baa55c95df308`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.2), which reported failed, 8 ok, 4 warning(s), 1 flag(s) across 13 checks. Full report: audit_report_after.json.

Verdict rule: any flag → failed · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
