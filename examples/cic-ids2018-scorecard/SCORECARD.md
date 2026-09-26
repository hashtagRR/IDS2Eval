# IDS2Eval Scorecard

**Dataset:** cic-ids2018
**Overall status:** ❌ Failed, 8 ok, 3 warning(s), 2 flag(s)
**Generated:** 2026-09-26T09:26:13.323126+00:00
**IDS2Eval version:** 0.1.0 (git 8cff297)
**Scorecard schema version:** 1.2
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 52,584 (13.15%); test rows leaking a train feature-match: 16,882 (16.88%); test-internal duplicates: 555 |
| 2 | `label_conflict_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label<br>*raw data:* 882 feature vector(s) (15,194 rows, 3.04%) map to more than one label. The ground truth contradicts itself for these rows; 481 of these span train and test |
| 3 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=8.6%, top2=15.4%)<br>*raw data:* no single feature or pair dominates importance (top1=8.9%, top2=16.4%) |
| 4 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'TotLen Fwd Pkts <= 21' reaches 86.9% test accuracy (86.2% train)<br>*raw data:* single rule 'Fwd Seg Size Min <= 30' reaches 83.0% test accuracy (83.2% train) |
| 5 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column: {'Dst Port': 0.912}. Suggest dropping: ['Dst Port']<br>*raw data:* standalone AUC by column: {'Dst Port': 0.925}. Suggest dropping: ['Dst Port'] |
| 6 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 7 | `homogeneity_test` | ✅ pass | 🚩 flag | *Evidence: statistical.* 9 classes tested; leakage signature (test significantly closer than control, p<0.05) in: ['Bot', 'DoS attacks-Slowloris']<br>*raw data:* 11 classes tested; test-to-train and train-internal proximity statistically indistinguishable for every class (consistent with inherent class homogeneity, not train/test leakage) |
| 8 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 15 classes, train imbalance ratio (majority:minority) = 149712:1; classes below 1% of train: ['SSH-Bruteforce', 'DoS attacks-GoldenEye', 'DoS attacks-Slowloris', 'DDOS attack-LOIC-UDP', 'DoS attacks-SlowHTTPTest', 'FTP-BruteForce', 'Brute Force -Web', 'Brute Force -XSS', 'SQL Injection']<br>*raw data:* 15 classes, train imbalance ratio (majority:minority) = 166034:1; classes below 1% of train: ['DoS attacks-SlowHTTPTest', 'DoS attacks-GoldenEye', 'DoS attacks-Slowloris', 'DDOS attack-LOIC-UDP', 'Brute Force -Web', 'Brute Force -XSS', 'SQL Injection'] |
| 9 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'Dst Port': 24978} |
| 10 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* missing values in 1 feature column(s); +-inf values in 2 feature column(s); 8 constant/near-constant feature(s) |
| 11 | `near_duplicate_class_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 11 classes tested<br>*raw data:* 475 of 5,317 sampled rows (8.93%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'DoS attacks-SlowHTTPTest / FTP-BruteForce': 474, 'Benign / DoS attacks-GoldenEye': 1} |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ⚠️ warn | *Evidence: documented.* The 2018-02-23 day-file's Brute-Force-Web/Brute-Force-XSS rows are approximately 41% mislabeled (ground-truth labeling error, not an extraction or pipeline bug). (Liu et al. 2022, IEEE CNS); An independent re-labeling audit measured a 7.53% overall label corruption rate, with some individual attack classes above 75%. (Cantone et al. 2024, IEEE Access) |

## What cleaning removed

- Train: 400,000 → 347,416 rows (52,584 duplicates dropped)
- Test: 100,000 → 82,563 rows (16,882 train-leaking rows and 555 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 400,000 · test rows: 100,000 · features: 78
- Train content hash: `d659a2f4841244f0beca91dbcf0f247f0ea8b4321167c34322a68319961cc886`
- Test content hash: `a993f8e271abf51a2d9ceb601b871397dbd5c8f202230779356987433c3cf281`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.2), which reported failed, 8 ok, 3 warning(s), 2 flag(s) across 13 checks. Full report: audit_report_after.json.

Verdict rule: any flag → failed · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
