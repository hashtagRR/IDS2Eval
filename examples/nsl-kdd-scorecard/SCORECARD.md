# IDS2Eval Scorecard

**Dataset:** nsl-kdd
**Overall status:** ❌ Failed, 9 ok, 3 warning(s), 1 flag(s)
**Generated:** 2026-09-26T08:53:14.613803+00:00
**IDS2Eval version:** 0.1.0 (git 8cff297)
**Scorecard schema version:** 1.2
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 16 (0.01%); test rows leaking a train feature-match: 664 (2.95%); test-internal duplicates: 47 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 116 feature vector(s) (247 rows, 0.17%) map to more than one label. The ground truth contradicts itself for these rows; 58 of these span train and test |
| 3 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=14.2%, top2=25.6%)<br>*raw data:* no single feature or pair dominates importance (top1=14.1%, top2=25.0%) |
| 4 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'same_srv_rate <= 0.495' reaches 63.4% test accuracy (84.0% train)<br>*raw data:* single rule 'same_srv_rate <= 0.495' reaches 62.7% test accuracy (84.0% train) |
| 5 | `identity_column_flag` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 6 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 7 | `homogeneity_test` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 12 classes tested; leakage signature (test significantly closer than control, p<0.05) in: ['smurf']<br>*raw data:* 12 classes tested; leakage signature (test significantly closer than control, p<0.05) in: ['ipsweep', 'smurf'] |
| 8 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 23 classes, train imbalance ratio (majority:minority) = 33670:1; classes below 1% of train: ['back', 'teardrop', 'warezclient', 'pod', 'guess_passwd', 'buffer_overflow', 'warezmaster', 'land', 'imap', 'rootkit', 'loadmodule', 'ftp_write', 'multihop', 'phf', 'perl', 'spy']<br>*raw data:* 23 classes, train imbalance ratio (majority:minority) = 33672:1; classes below 1% of train: ['back', 'teardrop', 'warezclient', 'pod', 'guess_passwd', 'buffer_overflow', 'warezmaster', 'land', 'imap', 'rootkit', 'loadmodule', 'ftp_write', 'multihop', 'phf', 'perl', 'spy'] |
| 9 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* no id_like_columns configured |
| 10 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 1 constant/near-constant feature(s) |
| 11 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 14 classes tested |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The test set intentionally includes attack types absent from the training set, by design, to test generalization to unknown attacks rather than memorization; this project's own audit of the official partition finds 17 such test-only attack types. (Tavallaee et al. 2009, IEEE CISDA) |

## What cleaning removed

- Train: 125,973 → 125,957 rows (16 duplicates dropped)
- Test: 22,544 → 21,833 rows (664 train-leaking rows and 47 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 125,973 · test rows: 22,544 · features: 41
- Train content hash: `8c7cf0a516450d17a5426bfb0efcf6839fb28ebaadf494f32c59e1d29bb25441`
- Test content hash: `cffa47019c555661fc1d3d2b2b45f11ead633d0dcadf618718c44c6e926916d0`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.2), which reported failed, 9 ok, 3 warning(s), 1 flag(s) across 13 checks. Full report: audit_report_after.json.

Verdict rule: any flag → failed · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
