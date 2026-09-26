# Example: ToN-IoT (NetFlow-V2) scorecard

A real IDS<sup>2</sup>Eval audit of
[NF-ToN-IoT-V2](https://www.kaggle.com/datasets/dhoogla/nftoniotv2), the
University of Queensland's NetFlow-V2 conversion of the original ToN-IoT
dataset - 41 flow features exported with the NetFlow v2 feature set rather
than ToN-IoT's original, much larger raw feature set. 13,135,881 flows total,
too large for this 7.8GB VM in full: a seeded, reproducible 500,000-row
reservoir sample, split 80/20 at random. Produced with `config.yaml` in this
folder; open [SCORECARD.html](SCORECARD.html) in a browser for the full
result, or read [SCORECARD.md](SCORECARD.md).

**Result: failed** - 9 ok, 2 warnings, 2 flags after dedup, across 13 checks.

What it found:

- **`identity_column_flag` finds `L4_DST_PORT` alone predicts the label at AUC
  0.896** - the same destination-port shortcut this tool has already found in
  the CIC-IDS2017/2018 examples, now reproduced on a IoT-traffic dataset built
  by a different lab with a different flow exporter. Suggests this is a
  property of NetFlow-style features in general, not one dataset's extraction
  bug.
- **`homogeneity_test` flags `dos` and `backdoor`** as significantly closer to
  train than a random split would predict, a leakage signature - with only
  19,761 (`dos`) and 496 (`backdoor`) train rows respectively, both are also
  the kind of small class where a handful of near-duplicate flows can trip
  this check; worth a closer look before trusting benchmark scores on either
  class.
- **`data_integrity_check` finds ±inf values** in `SRC_TO_DST_SECOND_BYTES`
  (2 rows) and `DST_TO_SRC_SECOND_BYTES` (3 rows) - division-by-zero in a
  throughput-rate feature when a flow's duration rounds to zero seconds, the
  same failure mode CIC-IDS2017's `Flow Bytes/s` has.
- **`schema_fingerprint_check` matches no known extractor signature** - this
  is NetFlow v2, not CICFlowMeter, so the CICFlowMeter-specific miscalculation
  caveat that applies to the CIC-family examples does not apply here.
- **No curated `known_issue_lookup` entries yet** for this dataset.
- **`near_duplicate_class_check` passes**: no near-zero-distance feature vector
  spans two different labels across the 10 classes with enough rows to test.
- **Severe imbalance**: 1,177:1 majority:minority, with `backdoor`, `mitm`,
  and `ransomware` each under 1% of train - `ransomware` has only 93 train
  rows in this 500K-row sample.

`Label`, the dataset's own binary 0/1 target for the same rows `Attack`
labels multi-class (with `Benign` as the negative class), is dropped via
`schema.drop_columns` rather than used as the audit's label - keeping it in
as a feature would hand the checks a column that is the answer itself.

How the data was obtained: `dhoogla/nftoniotv2` from Kaggle, downloaded
2026-09-25 via the Kaggle API's public dataset-download endpoint (no
authentication required). The single distributed parquet file was streamed
to gzip CSV in fixed-size batches rather than loaded into memory whole, since
this machine has 7.8GB of RAM and the file holds 13.1M rows.

Run on a 4-vCPU / 7.8GB VM: 9m 27s, audit only (`--skip-benchmark`), most of
it in the reservoir-sample pass over the full 13.1M-row file. Produced with
IDS2Eval at commit 2ef764e.

Files: `config.yaml` (input), `audit_report_before.json` /
`audit_report_after.json` (full findings), `dataset_fingerprint.json` /
`environment.json` (provenance), `SCORECARD.html` / `scorecard.json` /
`SCORECARD.md` (the citable rollup, see
[guide/checks.md](../../guide/checks.md#the-scorecard) for the format).
No `scorecard.pdf`/`.png`: matching the other examples, this one ships the
HTML scorecard only, the same thing the dashboard shows.
