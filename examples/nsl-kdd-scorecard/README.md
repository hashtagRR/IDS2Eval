# Example: NSL-KDD scorecard

A real IDS<sup>2</sup>Eval run on NSL-KDD: the official KDDTrain+/KDDTest+ pair (GitHub mirror, standard KDD'99 column names added), 148,517 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-10-07 at commit `be73293` with the frozen method (tag `paper-method-freeze`).
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 19 checks ran: 7 `ok`, 4 `warning`, 1 `flag`, and 7 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 16 training rows, 664 test rows that reuse a training feature vector, and 47 test-internal duplicates.

**Flags**

- `feature_auc_ranking_check`: 'wrong_fragment' alone reaches AUC 1.000 identifying 'teardrop'; a single feature this separable is worth checking for a leakage artifact.

**Warnings**

- `homogeneity_test`: 12 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['ipsweep', 'pod', 'buffer_overflow']; sample size isn't enough to tell for these classes.
- `class_distribution_report`: 23 classes, train imbalance ratio (majority:minority) = 33670:1; classes below 1% of train: ['back', 'teardrop', 'warezclient', 'pod', 'guess_passwd', 'buffer_overflow', 'warezmaster', 'land', 'imap', 'rootkit', 'loadmodule', 'ftp_write', 'multihop', 'phf', 'perl', 'spy'].
- `data_integrity_check`: 1 constant/near-constant feature(s).
- `known_issue_lookup`: The test set intentionally includes attack types absent from the training set, by design, to test generalization to unknown attacks rather than memorization; this project's own audit of the official partition finds 17 such test-only attack types. (Tavallaee et al. 2009, IEEE CISDA).

**Not applicable** (the config gives these checks no input column): `identity_column_flag`, `port_protocol_shortcut_check`, `temporal_leakage_check`, `temporal_realism_check`, `flow_group_leakage_check`, `scenario_holdout_falsification`, `low_cardinality_warning`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)).
