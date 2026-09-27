# Example: BoT-IoT (NetFlow-V2) scorecard

A real IDS<sup>2</sup>Eval audit of
[NF-BoT-IoT-V2](https://www.kaggle.com/datasets/dhoogla/nfbotiotv2), the
University of Queensland's NetFlow-V2 conversion of the original BoT-IoT
dataset - the same 41-feature NetFlow v2 export as this project's ToN-IoT
example, from a different lab's IoT testbed. 30,420,086 flows total, too
large for this 7.8GB VM in full: a seeded, reproducible 500,000-row
reservoir sample, split 80/20 at random. Produced with `config.yaml` in this
folder; open [SCORECARD.html](SCORECARD.html) in a browser for the full
result, or read [SCORECARD.md](SCORECARD.md).

**Result: failed** - 15 ok, 2 warnings, 2 flags after dedup, across 19
checks. This is a change from an earlier run of this same dataset, which
reported passed with warnings before `feature_auc_ranking_check` and
`port_protocol_shortcut_check` existed; see below.

What it found:

- **`port_protocol_shortcut_check` finds `L4_DST_PORT` combined with
  `PROTOCOL` reaches AUC 0.952, though `L4_DST_PORT` alone only reaches
  0.531** (see `identity_column_flag` below). The single-column check on its
  own understated this dataset's identity-leakage risk: port isn't a
  shortcut by itself here, but port-plus-protocol is a strong one, the
  reason this check exists as a complement to `identity_column_flag` rather
  than a redundant re-check of the same column.
- **`feature_auc_ranking_check` finds `SHORTEST_FLOW_PKT` alone reaches AUC
  0.990 identifying `DDoS`**, and it survives dedup - worth checking for a
  leakage artifact the same way the port/protocol pair above is.
- **`known_issue_lookup` warns the full dataset is over 99.9% attack
  traffic** (129,437 of 30,420,086 rows are benign, 0.43%) - and this run's
  own 500K-row uniform sample demonstrates exactly that risk: only 1,711
  train rows (0.43%) and 428 test rows are `Benign`, and `Theft` shrinks to
  37 train rows and 9 test rows. Any benchmark accuracy on this sample is
  mostly measuring attack-vs-attack discrimination, not real-traffic
  recognition.
- **`one_rule_check` finds `LONGEST_FLOW_PKT <= 34` alone reaches 90.8% test
  accuracy** (90.8% train) - consistent with published critiques that
  BoT-IoT's attack traffic is separable on packet-size features alone,
  though `leakage_screen` finds no single feature dominates importance
  (top1 = 12.2%), so this rule's accuracy leans heavily on the DDoS/DoS
  majority classes rather than a universal shortcut.
- **`identity_column_flag` finds `L4_DST_PORT` only reaches AUC 0.531 alone**
  - essentially uninformative by itself, unlike the CIC-family and ToN-IoT
  examples where destination port alone is already a severe shortcut. It
  takes `PROTOCOL` alongside it (`port_protocol_shortcut_check`, above) to
  reveal this dataset's version of the same leakage.
- **`homogeneity_test` and `data_integrity_check` both pass clean** - no
  leakage signature in any of the 4 classes tested, and no missing values,
  constant features, or ±inf found in this sample.
- **`schema_fingerprint_check` matches no known extractor signature** - this
  is NetFlow v2, not CICFlowMeter.
- **Extreme imbalance**: 5,065:1 majority:minority even before accounting
  for how thin `Benign` and `Theft` already are in the source data.
- **`near_duplicate_class_check` passes**: no near-zero-distance feature vector
  spans two different labels across the 5 classes with enough rows to test.

`Label`, the dataset's own binary 0/1 target for the same rows `Attack`
labels multi-class (with `Benign` as the negative class), is dropped via
`schema.drop_columns` rather than used as the audit's label, same as the
ToN-IoT example.

How the data was obtained: `dhoogla/nfbotiotv2` from Kaggle, downloaded
2026-09-25 via the Kaggle API's public dataset-download endpoint (no
authentication required). The single distributed parquet file (30.4M rows)
was streamed to gzip CSV in fixed-size batches rather than loaded into
memory whole, since this machine has 7.8GB of RAM.

Run on a 4-vCPU / 7.8GB VM, audit only (`--skip-benchmark`), most of it in
the reservoir-sample pass over the full 30.4M-row file. Re-run 2026-09-27
(on a 4-vCPU / 15GB VM) to pick up `feature_auc_ranking_check`,
`port_protocol_shortcut_check`, `row_order_leakage_check`, and
`temporal_realism_check` (the last one no-ops here, no
`schema.timestamp_column` configured), which is why the check count reads
19 and the verdict changed from `passed_with_warnings` to `failed` - two
genuinely new findings (above), not a change in any pre-existing result.
The reservoir sample is identical across runs (same seed, same source
file), confirmed by `identity_column_flag`'s exact-match AUC. Produced
with IDS2Eval at commit aa2be21.

Files: `config.yaml` (input), `audit_report_before.json` /
`audit_report_after.json` (full findings), `dataset_fingerprint.json` /
`environment.json` (provenance), `SCORECARD.html` / `scorecard.json` /
`SCORECARD.md` (the citable rollup, see
[guide/checks.md](../../guide/checks.md#the-scorecard) for the format).
No `scorecard.pdf`/`.png`: matching the other examples, this one ships the
HTML scorecard only, the same thing the dashboard shows.
