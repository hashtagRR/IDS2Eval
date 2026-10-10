# Example scorecards

Real IDS<sup>2</sup>Eval runs on seven widely used NIDS benchmarks: the frozen-code runs behind the paper's Tables 9 and 10. Each folder holds the configuration, the full audit reports and the scorecard. Counts are after deduplication; "n/a" counts checks that lacked an input column and are reported as `ok` by the tool.

| Dataset | Rows | ok | n/a | warning | flag | Flagged checks |
|---|---|---|---|---|---|---|
| [UNSW-NB15](unsw-nb15-scorecard/) | 257,673 | 9 | 7 | 2 | 1 | `row_order_leakage_check` |
| [NSL-KDD](nsl-kdd-scorecard/) | 148,517 | 7 | 7 | 4 | 1 | `feature_auc_ranking_check` |
| [CIC-IDS2017](cic-ids2017-scorecard/) | 2,830,743 | 7 | 5 | 4 | 3 | `near_duplicate_class_check`, `feature_auc_ranking_check`, `identity_column_flag` |
| [CSE-CIC-IDS2018](cic-ids2018-scorecard/) | 16,232,943 | 12 | 4 | 3 | 3 | `feature_auc_ranking_check`, `identity_column_flag`, `port_protocol_shortcut_check` |
| [CICDDoS2019](cic-ddos2019-scorecard/) | 70,427,637 | 7 | 4 | 4 | 4 | `feature_auc_ranking_check`, `identity_column_flag`, `port_protocol_shortcut_check`, `row_order_leakage_check` |
| [ToN-IoT](ton-iot-scorecard/) | 211,043 | 13 | 4 | 2 | 3 | `feature_auc_ranking_check`, `identity_column_flag`, `port_protocol_shortcut_check` |
| [BoT-IoT](bot-iot-scorecard/) | 3,668,522 | 14 | 2 | 3 | 3 | `one_rule_check`, `feature_auc_ranking_check`, `identity_column_flag` |

[CIC-IoT2023](cic-iot2023-scorecard/) is an older-code example on a dataset the paper later excluded.
