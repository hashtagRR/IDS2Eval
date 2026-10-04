# IDS2Eval Scorecard

**Dataset:** cic-iot2023
**Overall status:** 🚩 Review Required, 17 ok, 1 warning(s), 1 flag(s)
**Generated:** 2026-09-26T23:48:52.431922+00:00
**IDS2Eval version:** 0.1.0 (git ad380be)
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 85,882 (21.47%); test rows leaking a train feature-match: 31,607 (31.61%); test-internal duplicates: 1,266 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 16,898 feature vector(s) (67,916 rows, 13.58%) map to more than one label. The ground truth contradicts itself for these rows; 8,896 of these span train and test |
| 3 | `near_duplicate_class_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 8 classes tested<br>*raw data:* 2 of 3,340 sampled rows (0.06%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'DDoS / DoS': 1, 'Spoofing / Web': 1} |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=9.2%, top2=16.1%)<br>*raw data:* no single feature or pair dominates importance (top1=9.0%, top2=16.6%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'icmp <= 0.9592' reaches 22.6% test accuracy (24.5% train)<br>*raw data:* single rule 'icmp <= 0.955' reaches 26.8% test accuracy (26.9% train) |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'fin_count' alone reaches AUC 0.999 identifying 'DDoS-RSTFINFlood'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 8 | `port_protocol_shortcut_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no port-like entry in schema.id_like_columns and/or no proto-like column found, this check needs both |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ✅ pass | ✅ pass | *Evidence: statistical.* 8 classes tested; test-to-train and train-internal proximity statistically indistinguishable for every class (consistent with inherent class homogeneity, not train/test leakage) |
| 14 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 15 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 34 classes, train imbalance ratio (majority:minority) = 3030:1; classes below 1% of train: ['VulnerabilityScan', 'MITM-ArpSpoofing', 'DDoS-UDP_Fragmentation', 'DDoS-ACK_Fragmentation', 'DNS_Spoofing', 'Recon-HostDiscovery', 'Recon-OSScan', 'Recon-PortScan', 'DoS-HTTP_Flood', 'DDoS-HTTP_Flood', 'DDoS-SlowLoris', 'DictionaryBruteForce', 'BrowserHijacking', 'CommandInjection', 'SqlInjection', 'Backdoor_Malware', 'XSS', 'Recon-PingSweep', 'Uploading_Attack']<br>*raw data:* 34 classes, train imbalance ratio (majority:minority) = 4394:1; classes below 1% of train: ['DDoS-ICMP_Fragmentation', 'VulnerabilityScan', 'MITM-ArpSpoofing', 'DDoS-UDP_Fragmentation', 'DDoS-ACK_Fragmentation', 'DNS_Spoofing', 'Recon-HostDiscovery', 'Recon-OSScan', 'Recon-PortScan', 'DoS-HTTP_Flood', 'DDoS-HTTP_Flood', 'DDoS-SlowLoris', 'DictionaryBruteForce', 'BrowserHijacking', 'CommandInjection', 'SqlInjection', 'Backdoor_Malware', 'XSS', 'Recon-PingSweep', 'Uploading_Attack'] |
| 16 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 17 | `data_integrity_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no missing labels, constant features, or +-inf values found |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ✅ pass | *Evidence: documented.* no curated known issues for dataset 'cic-iot2023' |

## What cleaning removed

- Train: 400,000 → 314,118 rows (85,882 duplicates dropped)
- Test: 100,000 → 67,127 rows (31,607 train-leaking rows and 1,266 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 400,000 · test rows: 100,000 · features: 38
- Train content hash: `ef4de5ff972d07c55231ad3a4f487f32394d61fcded1b441fe594ca9abbaad6e`
- Test content hash: `8882a4f9f804c8e9ef964ab15795995241c49b3966c7bf2122547fa5d1a28123`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 17 ok, 1 warning(s), 1 flag(s) across 19 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
