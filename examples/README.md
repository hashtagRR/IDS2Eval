# Example scorecards

Real IDS<sup>2</sup>Eval runs on seven widely used NIDS benchmarks: the runs behind the paper's Table 12 and Supplement Table S14, made with version 0.2.0 (tag `paper-method-freeze`). Their wording is that version's: `homogeneity_test`'s excess matching was then called leakage, and verdicts were accuracy-only. From version 0.3.1, `feature_auc_ranking_check` also reports a value-lookup statistic and can flag through it, so a rerun can change that check's status. Each folder holds the configuration, the full audit reports and the scorecard. Counts are after deduplication; "n/a" counts checks with no input to test (status `not_applicable`, rescored from the archived reports under the v0.2.1 rule).

| Dataset | Rows | ok | n/a | warning | flag | Flagged checks |
|---|---|---|---|---|---|---|
| [UNSW-NB15](unsw-nb15-scorecard/) | 257,673 | 9 | 7 | 2 | 1 | `row_order_leakage_check` |
| [NSL-KDD](nsl-kdd-scorecard/) | 148,517 | 7 | 7 | 4 | 1 | `feature_auc_ranking_check` |
| [CIC-IDS2017](cic-ids2017-scorecard/) | 2,830,743 | 7 | 5 | 4 | 3 | `near_duplicate_class_check`, `feature_auc_ranking_check`, `identity_column_flag` |
| [CSE-CIC-IDS2018](cic-ids2018-scorecard/) | 16,232,943 | 12 | 4 | 3 | 3 | `feature_auc_ranking_check`, `identity_column_flag`, `port_protocol_shortcut_check` |
| [CICDDoS2019](cic-ddos2019-scorecard/) | 70,427,637 | 7 | 4 | 4 | 4 | `feature_auc_ranking_check`, `identity_column_flag`, `port_protocol_shortcut_check`, `row_order_leakage_check` |
| [ToN-IoT](ton-iot-scorecard/) | 211,043 | 13 | 4 | 2 | 3 | `feature_auc_ranking_check`, `identity_column_flag`, `port_protocol_shortcut_check` |
| [BoT-IoT](bot-iot-scorecard/) | 3,668,522 | 13 | 3 | 3 | 3 | `one_rule_check`, `feature_auc_ranking_check`, `identity_column_flag` |

[CIC-IoT2023](cic-iot2023-scorecard/) is an older-code example on a dataset the paper later excluded.
