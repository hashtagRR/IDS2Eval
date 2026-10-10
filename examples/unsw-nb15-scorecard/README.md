# Example: UNSW-NB15 scorecard

A real IDS<sup>2</sup>Eval run on UNSW-NB15: the official train/test pair (GitHub mirror, file names corrected by content), 257,673 rows. It is the run behind the paper's Tables 9 and 10 (Section 6), made on 2026-10-07 at commit `be73293` with the frozen method (tag `paper-method-freeze`).
`config.yaml` is the configuration it used, with data paths reduced to `data/<file>`. Read [SCORECARD.md](SCORECARD.md), or open [SCORECARD.html](SCORECARD.html) in a browser.

**Result: review required.** After deduplication, 19 checks ran: 9 `ok`, 2 `warning`, 1 `flag`, and 7 not applicable (the tool reports these as `ok`; see below).

**Deduplication** dropped 74,301 training rows, 8,541 test rows that reuse a training feature vector, and 21,147 test-internal duplicates.

**Flags**

- `row_order_leakage_check`: adjacent-row label-transition rate (train=0.09, test=0.00) as a share of what a randomly shuffled ordering would produce; test is the most contiguous, consistent with rows still in collection order rather than shuffled before this split.

**Warnings**

- `homogeneity_test`: 10 classes tested; inconclusive (95% CI straddles the +/-0.05 equivalence margin) for: ['Backdoor', 'Worms']; sample size isn't enough to tell for these classes.
- `known_issue_lookup`: Some redistributions invert the UNSW_NB15_training-set.csv/testing-set.csv file-name-to-content mapping relative to the dataset's documented convention (82,332 vs. 175,341 rows), verify against the published per-attack-category counts before trusting file names. (Independently verified in this project's own audit methodology).

**Not applicable** (the config gives these checks no input column): `identity_column_flag`, `port_protocol_shortcut_check`, `temporal_leakage_check`, `temporal_realism_check`, `flow_group_leakage_check`, `scenario_holdout_falsification`, `low_cardinality_warning`.

Files: `config.yaml` (input); `audit_report_before.json` and `audit_report_after.json` (every check's full output); `dataset_fingerprint.json` and `environment.json` (provenance); `scorecard.json`, `SCORECARD.md` and `SCORECARD.html` (the citable summary, format in [guide/checks.md](../../guide/checks.md#the-scorecard)).
