# IDS2Eval Scorecard

**Dataset:** ctu-13
**Overall status:** 🚩 Review Required, 14 ok, 1 warning(s), 6 flag(s), 3 not applicable
**Generated:** 2026-11-25T10:16:22.976755+00:00
**IDS2Eval version:** 0.2.3
**Scorecard schema version:** 1.4
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 6,508 (1.02%); test rows leaking a train feature-match: 2,675 (1.67%); test-internal duplicates: 256 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `near_duplicate_class_check` | ✅ pass | 🚩 flag | *Evidence: statistical.* 2 of 3,550 sampled rows (0.06%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'NSIS.ay / Sogou': 2}<br>*raw data:* no near-zero-distance feature vectors found across 8 classes tested |
| 4 | `leakage_screen` | ✅ pass | 🚩 flag | *Evidence: statistical.* 'SrcAddr' carries 56.3% of total split importance (standalone AUC=1.000). Check whether it's a leakage artifact rather than attack-behavior signal<br>*raw data:* no single feature or pair dominates importance (top1=44.0%, top2=55.6%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'SrcAddr <= 1.5' reaches 94.7% test accuracy (94.6% train), vs. 55.0% from always predicting the majority class<br>*raw data:* single rule 'SrcAddr <= 0.5' reaches 88.3% test accuracy (88.4% train), vs. 55.5% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | ✅ pass | ✅ pass | *Evidence: statistical.* 'TotPkts' alone reaches AUC 0.635 identifying 'normal'<br>*raw data:* 'TotPkts' alone reaches AUC 0.638 identifying 'normal' |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): SrcAddr: 1.0 (100.0%, 1.0), DstAddr: 0.904 (94.3%, 0.896), Sport: 0.999 (94.2%, 1.0), Dport: 0.823 (99.7%, 0.823). Suggest dropping: ['SrcAddr', 'DstAddr', 'Sport', 'Dport']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): SrcAddr: 1.0 (100.0%, 1.0), DstAddr: 0.904 (94.4%, 0.896), Sport: 0.999 (94.3%, 1.0), Dport: 0.825 (99.7%, 0.825). Suggest dropping: ['SrcAddr', 'DstAddr', 'Sport', 'Dport'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'Sport' + 'Proto' combined: 0.976. Port and protocol together may predict the label without attack behavior<br>*raw data:* standalone AUC of 'Sport' + 'Proto' combined: 0.977. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'StartTime' alone: 0.945. Timestamp alone may predict the label without learning attack behavior |
| 10 | `temporal_realism_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* narrowest class's own time span: 'Sogou' covers 0.1% of the full capture window; timestamp alone may act as a proxy for this class rather than its actual traffic behavior |
| 11 | `flow_group_leakage_check` | ⚪ n/a | ⚪ n/a | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ⚠️ warn | ✅ pass | *Evidence: statistical.* 7 classes tested; for every class the 95% CI upper bound on (test-to-train minus train-internal) near-duplicate rate is below the +0.05 margin, so no class shows excess cross-boundary matching<br>*raw data:* 7 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['normal']; sample size isn't enough to tell for these classes |
| 14 | `resplit_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9999, grouped-split accuracy=1.0000 (drop=-0.0001); balanced accuracy drop=-0.0001, macro-F1 drop=-0.0001 (accuracy not material, balanced accuracy not material, macro f1 not material); grouping key: 490,950 groups over 801,132 rows (1.63 rows per group, 52.7% of rows in single-row groups); the grouped split reproduces the random-split result: no evidence that information tied to the grouping key drives it (other grouping keys and shortcuts are not tested) |
| 15 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9999, holding out scenario '7.0' entirely: accuracy=0.9971 (drop=+0.0028); balanced accuracy drop=+0.0014, macro-F1 drop=+0.0197 (accuracy not material, balanced accuracy not material, macro f1 not material) |
| 16 | `class_distribution_report` | ✅ pass | ✅ pass | *Evidence: statistical.* 2 classes, train imbalance ratio (majority:minority) = 1:1 |
| 17 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'SrcAddr': 58, 'DstAddr': 43886, 'Sport': 94865, 'Dport': 2524} |
| 18 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* missing values in 5 feature column(s); 1 constant/near-constant feature(s) |
| 19 | `cross_capture_matrix_check` | ⚪ n/a (same on raw and cleaned data) | *Evidence: direct experiment.* skipped, 13 eligible scenarios exceeds the 6-scenario cap |
| 20 | `result_robustness_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.9662 (identity_columns_dropped) to 1.0000 (grouped_split) across 4 conditions, a spread of 0.0337 (sampling margin +/-0.0009); balanced accuracy spread 0.0345, macro-F1 spread 0.0342; accuracy not material, balanced accuracy not material, macro f1 not material |
| 21 | `reuse_removal_falsification` | ✅ pass | ⚪ n/a | *Evidence: direct experiment.* no training row shares a feature vector with a test row, nothing to remove<br>*raw data:* removing the 4,585 training rows that share a feature vector with a test row, against removing as many random rows of the same classes, over 10 seeds: score difference on the unchanged test set, mean [95% CI], accuracy -0.0000 [-0.0002, +0.0002], balanced accuracy -0.0000, macro-F1 -0.0000 (accuracy not material, balanced accuracy not material, macro f1 not material); on the 2,675 reused test rows alone, accuracy +0.0000 |
| 22 | `repeated_seed_falsification_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* grouped-split drop across 10 seeds, mean [95% CI]: accuracy +0.0009 [-0.0004, +0.0023], balanced accuracy +0.0008 [-0.0004, +0.0020], macro-F1 +0.0009 [-0.0005, +0.0023]; accuracy not material, balanced accuracy not material, macro f1 not material; overall not material on accuracy, balanced_accuracy, macro_f1 |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ✅ pass | *Evidence: documented.* no curated known issues for dataset 'ctu-13' |

## Not run

Disabled in this run's config, so they produced no result and say nothing about the dataset. Checks marked n/a above ran but had no input to test. `synthetic_realism_check`, `cross_dataset_drift_check`, `feature_category_ablation_check`, `artifact_sensitivity_check`, `seed_sensitivity_check`.

## What cleaning removed

- Train: 640,905 → 634,397 rows (6,508 duplicates dropped)
- Test: 160,227 → 157,296 rows (2,675 train-leaking rows and 256 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 640,905 · test rows: 160,227 · features: 13
- Train content hash: `a39961d28d0b1148dccf990a3aae4d204f2deefa292e519975daba4c4d2d85e8`
- Test content hash: `230576ae3b01d508d46cd1b95ce3fc83111d8ade9bf057c960edd7b449ad7d06`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.2.3 (scorecard schema 1.4), which reported review required, 14 ok, 1 warning(s), 6 flag(s), 3 not applicable across 24 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed; not applicable checks never change the verdict; if no check produced a result → not evaluated.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
