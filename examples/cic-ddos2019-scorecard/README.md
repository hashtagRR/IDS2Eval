# Example: CICDDoS2019 scorecard

A real IDS<sup>2</sup>Eval run on CICDDoS2019: the full official release, training day against testing day, 70,427,637 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-10-07 with the frozen method (tag `paper-method-freeze`).
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 19 checks ran: 7 `ok`, 4 `warning`, 4 `flag`, and 4 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 2,184,498 training rows, 244 test rows that reuse a training feature vector, and 650,949 test-internal duplicates.

**Flags**

- `feature_auc_ranking_check`: 'Total Length of Fwd Packets' alone reaches AUC 0.995 identifying 'Syn'; a single feature this separable is worth checking for a leakage artifact.
- `identity_column_flag`: standalone AUC by column (seen-value coverage, AUC on seen values): Source IP: 1.0 (99.9%, 1.0), Destination IP: 0.889 (0.2%, 1.0), Source Port: 0.825 (100.0%, 0.825), Destination Port: 0.935 (100.0%, 0.935). Suggest dropping: ['Source IP', 'Destination IP', 'Source Port', 'Destination Port'].
- `port_protocol_shortcut_check`: standalone AUC of 'Source Port' + 'Protocol' combined: 0.839. Port and protocol together may predict the label without attack behavior.
- `row_order_leakage_check`: adjacent-row label-transition rate (train=0.00, test=0.00) as a share of what a randomly shuffled ordering would produce; train is the most contiguous, consistent with rows still in collection order rather than shuffled before this split.

**Warnings**

- `class_distribution_report`: 13 classes, train imbalance ratio (majority:minority) = 41936:1; classes below 1% of train: ['UDP-lag', 'BENIGN', 'WebDDoS'].
- `schema_fingerprint_check`: matched extractor signature(s): ['CICFlowMeter'].
- `data_integrity_check`: missing values in 1 feature column(s); +-inf values in 2 feature column(s); 12 constant/near-constant feature(s).
- `known_issue_lookup`: By design, the two collection days cover different attack sets: the testing day includes several DDoS types absent from the training day (e.g. DNS, NTP, SNMP, TFTP, WebDDoS reflection attacks), so a classifier trained only on the training day has never seen those attack types. (Sharafaldin et al. 2019, IEEE ICCST); The same attack type is labeled inconsistently between the two days (e.g. training's 'UDPLag'/'MSSQL' vs. testing's 'UDP-lag'/'DrDoS_MSSQL'), so label strings must be remapped before any train/test comparison, not matched literally. (Independently verified in this project's own audit methodology).

**Not applicable** (the config gives these checks no input column): `temporal_leakage_check`, `temporal_realism_check`, `flow_group_leakage_check`, `scenario_holdout_falsification`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)).
