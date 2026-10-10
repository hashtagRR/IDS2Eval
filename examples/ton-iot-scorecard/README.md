# Example: ToN-IoT scorecard

A real IDS<sup>2</sup>Eval run on ToN-IoT: the official `Train_Test_Network.csv`, split 80/20 at random by IDS2Eval, with 10-seed falsification, 211,043 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-10-07 at commit `be73293` with the frozen method (tag `paper-method-freeze`).
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 22 checks ran: 13 `ok`, 2 `warning`, 3 `flag`, and 4 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 15,168 training rows, 5,185 test rows that reuse a training feature vector, and 216 test-internal duplicates.

**Flags**

- `feature_auc_ranking_check`: 'src_port' alone reaches AUC 0.952 identifying 'dos'; a single feature this separable is worth checking for a leakage artifact.
- `identity_column_flag`: standalone AUC by column (seen-value coverage, AUC on seen values): src_ip: 0.911 (100.0%, 0.911), dst_ip: 0.891 (99.8%, 0.891), src_port: 0.856 (96.6%, 0.86), dst_port: 0.924 (99.9%, 0.924). Suggest dropping: ['src_ip', 'dst_ip', 'src_port', 'dst_port'].
- `port_protocol_shortcut_check`: standalone AUC of 'src_port' + 'proto' combined: 0.865. Port and protocol together may predict the label without attack behavior.

**Warnings**

- `homogeneity_test`: 10 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['dos']; sample size isn't enough to tell for these classes.
- `class_distribution_report`: 10 classes, train imbalance ratio (majority:minority) = 41:1; classes below 1% of train: ['mitm'].

**Not applicable** (the config gives these checks no input column): `temporal_leakage_check`, `temporal_realism_check`, `flow_group_leakage_check`, `scenario_holdout_falsification`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)); `intervention_manifest.json` (the falsification checks' conditions).
