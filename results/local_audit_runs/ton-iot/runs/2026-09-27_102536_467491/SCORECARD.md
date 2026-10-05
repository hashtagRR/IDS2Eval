# IDS2Eval Scorecard

**Dataset:** ton-iot
**Overall status:** 🚩 Review Required, 15 ok, 2 warning(s), 4 flag(s)
**Generated:** 2026-09-27T10:59:06.372735+00:00
**IDS2Eval version:** 0.1.0 (git e47f6e9)
**Scorecard schema version:** 1.3
**Verdict judged on:** cleaned data (exact duplicates removed)

A full, styled version of this scorecard is in `SCORECARD.html`.

## Checks

Findings from this run's own data. Each one can, in principle, be reacted to - by dropping a column, resampling, switching split modes, or just noting the caveat.

| # | Check | Raw data | Cleaned data | Summary |
|---|---|---|---|---|
| 1 | `dedup_check` | ✅ pass | ✅ pass | *Evidence: statistical.* train duplicates: 0 (0.00%); test rows leaking a train feature-match: 0 (0.00%); test-internal duplicates: 0 |
| 2 | `label_conflict_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no feature vector maps to more than one label |
| 3 | `near_duplicate_class_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no near-zero-distance feature vectors found across 10 classes tested |
| 4 | `leakage_screen` | ✅ pass | ✅ pass | *Evidence: statistical.* no single feature or pair dominates importance (top1=9.4%, top2=17.4%) |
| 5 | `one_rule_check` | ✅ pass | ✅ pass | *Evidence: statistical.* single rule 'L4_DST_PORT <= 443.5' reaches 40.3% test accuracy (40.4% train) |
| 6 | `feature_auc_ranking_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 'OUT_PKTS' alone reaches AUC 0.992 identifying 'backdoor'; a single feature this separable is worth checking for a leakage artifact |
| 7 | `identity_column_flag` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC by column: {'L4_DST_PORT': 0.896}. Suggest dropping: ['L4_DST_PORT'] |
| 8 | `port_protocol_shortcut_check` | 🚩 flag | 🚩 flag | *Evidence: statistical.* standalone AUC of 'L4_DST_PORT' + 'PROTOCOL' combined: 0.898. Port and protocol together may predict the label without attack behavior |
| 9 | `temporal_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 10 | `temporal_realism_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.timestamp_column configured |
| 11 | `flow_group_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* no schema.flow_id_columns configured |
| 12 | `row_order_leakage_check` | ✅ pass | ✅ pass | *Evidence: statistical.* adjacent-row label-transition rate (train=1.00, test=1.00) as a share of what a randomly shuffled ordering would produce |
| 13 | `homogeneity_test` | 🚩 flag | 🚩 flag | *Evidence: statistical.* 10 classes tested; leakage signature (test significantly closer than control, p<0.05) in: ['dos', 'backdoor'] |
| 14 | `resplit_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* random-split accuracy=0.9648, grouped-split accuracy=0.9640 (drop=+0.0008); grouped split reproduces random-split accuracy, consistent with inherent class homogeneity rather than a split-artifact explanation |
| 15 | `scenario_holdout_falsification` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* no schema.scenario_column configured |
| 16 | `class_distribution_report` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* 10 classes, train imbalance ratio (majority:minority) = 1177:1; classes below 1% of train: ['backdoor', 'mitm', 'ransomware'] |
| 17 | `low_cardinality_warning` | ✅ pass | ✅ pass | *Evidence: statistical.* unique values by column: {'L4_DST_PORT': 49397} |
| 18 | `data_integrity_check` | ⚠️ warn | ⚠️ warn | *Evidence: statistical.* +-inf values in 2 feature column(s) |
| 19 | `result_robustness_check` | ✅ pass (same on raw and cleaned data) | *Evidence: direct experiment.* accuracy ranges from 0.9640 (grouped_split) to 0.9648 (random_split) across 3 conditions, a spread of 0.0008 |

## Known issues

Documented facts about this dataset or the tool that produced it, from published research - not measured from this run's data, and nothing in this run's config can fix what they report.

| # | Check | Status | Summary |
|---|---|---|---|
| 1 | `schema_fingerprint_check` | ✅ pass | *Evidence: documented.* no known extractor signature matched |
| 2 | `known_issue_lookup` | ✅ pass | *Evidence: documented.* no curated known issues for dataset 'ton-iot' |

## What cleaning removed

- Train: 400,000 → 400,000 rows (0 duplicates dropped)
- Test: 100,000 → 100,000 rows (0 train-leaking rows and 0 test-internal duplicates dropped)

## Compared to the previous run

Compared to `2026-09-27_023719_055559` (2026-09-27T02:48:11.150861+00:00).
No check's status changed since the previous run.

## Dataset fingerprint

- Train rows: 400,000 · test rows: 100,000 · features: 41
- Train content hash: `03587bbee696fad295803a852004fc276e4ce227ac99539751cad0733c7034ef`
- Test content hash: `c737a0aff65db970152f95dff7e8f39d87f7b5a44bb4771146eef487884049f0`

## Citing this result

> This result was obtained on a dataset audited with IDS2Eval v0.1.0 (scorecard schema 1.3), which reported review required, 15 ok, 2 warning(s), 4 flag(s) across 21 checks. Full report: audit_report_after.json.

Verdict rule: any flag → review required · warnings only → passed with warnings · all ok → passed.

---
*Scorecard format inspired by structured dataset-documentation practices. Datasheets for Datasets ([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and scorecards for synthetic data evaluation ([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)).*
