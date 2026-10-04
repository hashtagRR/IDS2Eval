# Example: ToN-IoT (official) scorecard

A real IDS<sup>2</sup>Eval audit of
[`Train_Test_Network.csv`](https://research.unsw.edu.au/projects/toniot-datasets),
the official UNSW/Moustafa ToN-IoT artifact most published ToN-IoT papers
actually train and report on - real `src_ip`/`dst_ip`/`src_port`/`dst_port`
columns included, unlike the University of Queensland NetFlow-V2 conversion
this example used previously (still available as `ton-iot.yaml` in
[configs/](../../configs/)). 211,043 rows total, small enough to load in
full: no reservoir sampling needed at all. Produced with `config.yaml` in
this folder; open [SCORECARD.html](SCORECARD.html) in a browser for the full
result, or read [SCORECARD.md](SCORECARD.md).

**Result: review required** - 18 ok, 1 warning, 3 flags after dedup, across 28 checks.

What it found:

- **Before dedup: 15,168 train duplicates (8.98%), 5,185 test rows leaking a
  train feature-match (12.28%), 216 test-internal duplicates** - 20,569 rows
  total (9.7% of the raw 211,043), all removed before the "after" audit
  runs. This is a deliberately class-balanced curated subset (50,000 normal
  + exactly 20,000 of each of 8 attack types + 1,043 mitm), not a
  natural-frequency sample of the full ~13M-row ToN-IoT Network capture, and
  duplication at this rate is a real property of that curation, not a
  pipeline artifact.
- **`identity_column_flag` finds all four IP/port columns predictive**
  (`src_ip` AUC 0.911, `dst_ip` 0.891, `src_port` 0.816, `dst_port` 0.925) -
  a much stronger identity-leakage signal than the NetFlow-V2 example ever
  showed, because this release keeps the real IPs the NetFlow conversion
  drops. `port_protocol_shortcut_check` finds `src_port` + `proto` combined
  reaches AUC 0.865. `feature_auc_ranking_check` finds `src_port` alone
  already reaches AUC 0.952 identifying `dos`.
- **`resplit_falsification` and `repeated_seed_falsification_check` both
  clear this**, though: grouping the split by the real 5-tuple
  (`src_ip`/`src_port`/`dst_ip`/`dst_port`/`proto`) barely moves accuracy
  (0.9949 random vs. 0.9945 grouped, a 0.04-point drop), and repeating that
  comparison across 10 seeds gives a mean drop of +0.0002 with a 95% CI of
  [-0.0002, +0.0006] - comfortably below the 1-point materiality threshold
  either way. The strong standalone AUCs above are a same-flow-features
  risk (`identity_column_flag`'s job to catch), not evidence of
  session-correlated train/test leakage (`resplit_falsification`'s job) -
  this dataset shows one without the other.
- **`result_robustness_check` finds a real spread**: accuracy ranges from
  0.9758 (identity columns dropped) to 0.9949 (random split) across 4
  conditions - a 1.9-point spread consistent with the identity-column
  leakage risk above; the model still performs well without the IP/port
  columns, but noticeably worse.
- **`homogeneity_test` passes clean** across all 10 classes - no leakage
  signature, consistent with the falsification checks above.
- **No curated `known_issue_lookup` entries yet** for this dataset name.
- **Severe imbalance**: 41:1 majority:minority, with `mitm` under 1% of
  train.

`label`, the dataset's own binary 0/1 target for the same rows `type`
already labels multi-class (with `normal` as the negative class), is
dropped via `schema.drop_columns` rather than used as the audit's label.

How the data was obtained: downloaded directly from the HuggingFace mirror
`codymlewis/TON_IoT_network` (`train_test_network.csv`), gzipped
immediately, original uncompressed file deleted. 211,043 rows confirmed via
direct inspection; class distribution confirmed deliberately balanced
(50,000 normal + 20,000 of each of 8 attack types + 1,043 mitm) before any
check ran.

Run on a local dev VM, audit only (`--skip-benchmark`), full file, no
chunking or sampling needed. Produced with IDS2Eval at commit `e47f6e9`.

Files: `config.yaml` (input), `audit_report_before.json` /
`audit_report_after.json` (full findings), `dataset_fingerprint.json` /
`environment.json` (provenance), `SCORECARD.html` / `scorecard.json` /
`SCORECARD.md` (the citable rollup, see
[guide/checks.md](../../guide/checks.md#the-scorecard) for the format).
No `scorecard.pdf`/`.png`: matching the other examples, this one ships the
HTML scorecard only, the same thing the dashboard shows.
