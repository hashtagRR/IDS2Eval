# Example: CSE-CIC-IDS2018 scorecard

A real IDS<sup>2</sup>Eval run on CSE-CIC-IDS2018: all ten official AWS day-files, split 80/20 at random by IDS2Eval, with 10-seed falsification, 16,232,943 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-09-29; the dataset has no string features, so later encoding fixes do not change it.
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 22 checks ran: 12 `ok`, 3 `warning`, 3 `flag`, and 4 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 3,703,769 training rows, 1,065,936 test rows that reuse a training feature vector, and 16,229 test-internal duplicates.

**Flags**

- `feature_auc_ranking_check`: 'Fwd Act Data Pkts' alone reaches AUC 1.000 identifying 'DDOS attack-LOIC-UDP'; a single feature this separable is worth checking for a leakage artifact.
- `identity_column_flag`: standalone AUC by column: {'Dst Port': 0.93}. Suggest dropping: ['Dst Port'].
- `port_protocol_shortcut_check`: standalone AUC of 'Dst Port' + 'Protocol' combined: 0.930. Port and protocol together may predict the label without attack behavior.

**Warnings**

- `class_distribution_report`: 15 classes, train imbalance ratio (majority:minority) = 316063:1; classes below 1% of train: ['Infilteration', 'SSH-Bruteforce', 'DoS attacks-GoldenEye', 'DoS attacks-Slowloris', 'DDOS attack-LOIC-UDP', 'Brute Force -Web', 'Brute Force -XSS', 'SQL Injection', 'FTP-BruteForce', 'DoS attacks-SlowHTTPTest'].
- `data_integrity_check`: missing values in 1 feature column(s); +-inf values in 2 feature column(s); 8 constant/near-constant feature(s).
- `known_issue_lookup`: The 2018-02-23 day-file's Brute-Force-Web/Brute-Force-XSS rows are approximately 41% mislabeled (ground-truth labeling error, not an extraction or pipeline bug). (Liu et al. 2022, IEEE CNS); An independent re-labeling audit measured a 7.53% overall label corruption rate, with some individual attack classes above 75%. (Cantone et al. 2024, IEEE Access).

**Not applicable** (the config gives these checks no input column): `temporal_leakage_check`, `temporal_realism_check`, `flow_group_leakage_check`, `scenario_holdout_falsification`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)); `intervention_manifest.json` (the falsification checks' conditions).
