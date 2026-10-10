# Example: CIC-IDS2017 scorecard

A real IDS<sup>2</sup>Eval run on CIC-IDS2017: the MachineLearningCSV day-files (Hugging Face mirror), split 80/20 at random by IDS2Eval, 2,830,743 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-10-07 at commit `be73293` with the frozen method (tag `paper-method-freeze`).
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 19 checks ran: 7 `ok`, 4 `warning`, 3 `flag`, and 5 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 247,799 training rows, 81,604 test rows that reuse a training feature vector, and 2,516 test-internal duplicates.

**Flags**

- `near_duplicate_class_check`: 2 of 6,029 sampled rows (0.03%) have a near-zero-distance neighbor under a different label. Most affected pairs: {'DoS Slowhttptest / DoS slowloris': 2}.
- `feature_auc_ranking_check`: 'Bwd Packet Length Max' alone reaches AUC 1.000 identifying 'Heartbleed'; a single feature this separable is worth checking for a leakage artifact.
- `identity_column_flag`: standalone AUC by column (seen-value coverage, AUC on seen values): Destination Port: 0.936 (99.4%, 0.935). Suggest dropping: ['Destination Port'].

**Warnings**

- `class_distribution_report`: 15 classes, train imbalance ratio (majority:minority) = 185530:1; classes below 1% of train: ['DoS GoldenEye', 'FTP-Patator', 'DoS slowloris', 'DoS Slowhttptest', 'SSH-Patator', 'Bot', 'Web Attack � Brute Force', 'Web Attack � XSS', 'Infiltration', 'Web Attack � Sql Injection', 'Heartbleed'].
- `schema_fingerprint_check`: matched extractor signature(s): ['CICFlowMeter'].
- `data_integrity_check`: missing values in 1 feature column(s); +-inf values in 2 feature column(s); 8 constant/near-constant feature(s).
- `known_issue_lookup`: The traffic capture has packet misorder and duplication, and some attacks that were actually launched are not correctly labeled as attack traffic in the released CSVs. (Engelen et al. 2021, IEEE S&P Workshops (WTMC)); A full re-labeling of the original release found 6.67% of labels wrong, with the error rate above 75% for some attack classes. (Liu et al. 2022, IEEE CNS (rates as summarized by Cantone et al. 2024)); Heartbleed has only 11 rows (about 0.0004% of the dataset), too few to evaluate reliably regardless of labeling accuracy. (Cantone et al. 2024, IEEE Access, Table 1).

**Not applicable** (the config gives these checks no input column): `port_protocol_shortcut_check`, `temporal_leakage_check`, `temporal_realism_check`, `flow_group_leakage_check`, `scenario_holdout_falsification`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)).
