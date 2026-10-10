# Example: BoT-IoT scorecard

A real IDS<sup>2</sup>Eval run on BoT-IoT: the authors' 5%-reduced, all-features release (OpenML), split 80/20 at random by IDS2Eval, with 10-seed falsification, 3,668,522 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-10-07 with the frozen method (tag `paper-method-freeze`).
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 22 checks ran: 14 `ok`, 3 `warning`, 3 `flag`, and 2 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 0 training rows, 0 test rows that reuse a training feature vector, and 0 test-internal duplicates.

**Flags**

- `one_rule_check`: single rule 'ltime <= 1.528e+09' reaches 97.5% test accuracy (97.5% train), vs. 52.5% from always predicting the majority class. This problem may be solvable without learning attack behavior.
- `feature_auc_ranking_check`: 'stime' alone reaches AUC 1.000 identifying 'Theft'; a single feature this separable is worth checking for a leakage artifact.
- `identity_column_flag`: standalone AUC by column (seen-value coverage, AUC on seen values): saddr: 0.522 (100.0%, 0.522), daddr: 0.865 (100.0%, 0.865), sport: 0.404 (100.0%, 0.404), dport: 0.536 (99.9%, 0.536). Suggest dropping: ['daddr'].

**Warnings**

- `class_distribution_report`: 5 classes, train imbalance ratio (majority:minority) = 24465:1; classes below 1% of train: ['Normal', 'Theft'].
- `low_cardinality_warning`: unique values by column: {'saddr': 21, 'daddr': 81, 'sport': 65541, 'dport': 6914}. ['saddr'] have fewer than 50 unique values, risk of memorizing specific hosts rather than learning attack behavior.
- `known_issue_lookup`: The full original (non-NetFlow) release is over 99.9% attack traffic (benign flows are 477 of 3,668,522 rows, 0.013%), even more skewed than the NetFlow-V2 conversion of this dataset; a classifier's accuracy on this data mostly reflects its attack-vs-attack discrimination, not its ability to recognize normal traffic. (Koroniotis et al. 2019, Future Generation Computer Systems).

**Not applicable** (the config gives these checks no input column): `flow_group_leakage_check`, `scenario_holdout_falsification`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)); `intervention_manifest.json` (the falsification checks' conditions).
