# IDS2Eval Scorecard

**Dataset:** ton-iot-official
**Overall status:** 🚩 Review Required, 17 ok, 2 warning(s), 3 flag(s)
**Generated:** 2026-10-07T11:14:07.683906+00:00
**IDS2Eval version:** 0.1.0 (git be73293)
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

<img src="scorecard.png" alt="IDS2Eval Scorecard" width="760">

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | 🚩 flag | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0<br>*raw data:* train duplicates: 15,168 (8.98%); test rows leaking a train feature-match: 5,185 (12.28%); test-internal duplicates: 216 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 10 classes tested |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=13.8%, top2=24.5%)<br>*raw data:* no single feature or pair dominates importance (top1=15.8%, top2=28.5%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'src_ip <= 3.5' reaches 31.7% test accuracy (30.5% train), vs. 22.7% from always predicting the majority class<br>*raw data:* single rule 'src_ip <= 7.5' reaches 23.7% test accuracy (23.7% train), vs. 23.7% from always predicting the majority class |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'src_port' alone reaches AUC 0.952 identifying 'dos'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column (seen-value coverage, AUC on seen values): src_ip: 0.911 (100.0%, 0.911), dst_ip: 0.891 (99.8%, 0.891), src_port: 0.856 (96.6%, 0.86), dst_port: 0.924 (99.9%, 0.924). Suggest dropping: ['src_ip', 'dst_ip', 'src_port', 'dst_port']<br>*raw data:* standalone AUC by column (seen-value coverage, AUC on seen values): src_ip: 0.925 (100.0%, 0.925), dst_ip: 0.896 (99.9%, 0.897), src_port: 0.878 (97.0%, 0.882), dst_port: 0.931 (99.9%, 0.931). Suggest dropping: ['src_ip', 'dst_ip', 'src_port', 'dst_port'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'src_port' + 'proto' combined: 0.865. Port and protocol together may predict the label without attack behavior<br>*raw data:* standalone AUC of 'src_port' + 'proto' combined: 0.881. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 10 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['dos']; sample size isn't enough to tell for these classes<br>*raw data:* 10 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['normal', 'dos']; sample size isn't enough to tell for these classes |
| 14 | `resplit_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9951, grouped-split accuracy=0.9947 (drop=+0.0004); grouped split reproduces random-split accuracy, consistent with inherent class homogeneity rather than a split-artifact explanation |
| 15 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 16 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 10 classes, train imbalance ratio (majority:minority) = 41:1; classes below 1% of train: ['mitm']<br>*raw data:* 10 classes, train imbalance ratio (majority:minority) = 48:1; classes below 1% of train: ['mitm'] |
| 17 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'src_ip': 51, 'dst_ip': 699, 'src_port': 25548, 'dst_port': 2013} |
| 18 | `data_integrity_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no missing labels, constant features, or +-inf values found |
| 19 | `result_robustness_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.9759 (identity_columns_dropped) to 0.9951 (random_split) across 4 conditions, a spread of 0.0192 (sampling margin +/-0.0016) |
| 20 | `repeated_seed_falsification_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* grouped-split accuracy drop across 10 seeds: mean=+0.0001, 95% CI=[-0.0003, +0.0006]; not material: even the most generous estimate in the 95% CI (+0.0006) stays below the +0.0100 materiality threshold |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ✅ pass | *Evidence: documented.* no curated known issues for dataset 'ton-iot-official' |

## What cleaning removed

- Train: 168,834 → 153,666 rows (15,168 duplicates dropped)
- Test: 42,209 → 36,808 rows (5,185 train-leaking rows and 216 test-internal duplicates dropped)

## Dataset fingerprint

- Train rows: 168,834 · test rows: 42,209 · features: 42
- Train content hash: `47f0dfab4681241185c00ecefcc77b68dfe37cc26f76c5380c33e53339ed3a44`
- Test content hash: `608174b3c2ddaf8b04d6b961198f940f883cce98c01e74796ccc785af7e27f5e`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 17 ok, 2 warning(s), 3 flag(s) across 22 checks. Full report: audit_report_after.json. A vector figure of this chart is at `scorecard.pdf`, ready to cite directly.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
