# Example: BoT-IoT (official) scorecard

A real IDS<sup>2</sup>Eval audit of the
[official UNSW/Koroniotis et al. "5% reduced, all-features" BoT-IoT
release](https://research.unsw.edu.au/projects/bot-iot-dataset), sourced
directly via OpenML dataset 42072 - the artifact most published BoT-IoT
papers actually train and report on, real `saddr`/`daddr`/`sport`/`dport`
columns included, unlike the University of Queensland NetFlow-V2 conversion
this example used previously (still available as `bot-iot.yaml` in
[configs/](../../configs/)). 3,668,522 rows total, the field's own "5%
reduced" convention, not a sample we chose - no reservoir sampling needed.
Produced with `config.yaml` in this folder; open
[SCORECARD.html](SCORECARD.html) in a browser for the full result, or read
[SCORECARD.md](SCORECARD.md).

**Result: review required** - 16 ok, 3 warnings, 3 flags after dedup, across 22
checks.

What it found:

- **The cleanest possible falsification outcome the framework can
  produce**: `resplit_falsification` finds random-split and grouped-split
  accuracy both exactly **1.0000**, a 0.0000 gap. `result_robustness_check`'s
  spread across all buildable conditions is likewise 0.0000, and
  `repeated_seed_falsification_check` confirms this across 10 seeds with a
  95% CI of [-0.0000, +0.0000] - not merely "not material," but no
  measurable sensitivity to split methodology at all, at the dataset's true
  full scale.
- **A serious, specific shortcut-learning finding, independent of the
  falsification question**: `one_rule_check` finds a single rule on `ltime`
  (flow end-time) alone reaching 97.5% accuracy, and `feature_auc_ranking_check`
  finds `ltime` alone reaches a perfect AUC of 1.000 identifying the
  `Theft` class - a scenario-timing artifact (the same family as this
  project's own UNSW-NB15 TTL finding and CIC-IDS2018 window-size finding),
  newly identified here rather than corroborated from prior work.
- **`identity_column_flag` flags `daddr`** (destination IP) at AUC 0.865 -
  `saddr`/`sport`/`dport` all stay well below the flag threshold.
  `low_cardinality_warning` shows only 21 distinct source IPs across the
  entire dataset, consistent with a small, fixed testbed topology.
- **`known_issue_lookup` warns the full original release is over 99.9%
  attack traffic** (only 477 of 3,668,522 rows are `Normal`, 0.013%) - even
  more skewed than the NetFlow-V2 conversion's own 0.43% benign share. Any
  benchmark accuracy on this data mostly reflects attack-vs-attack
  discrimination, not real-traffic recognition.
- **Extreme imbalance**: 24,465:1 majority:minority, with `Normal` and
  `Theft` both under 1% of train.
- **`dedup_check`, `homogeneity_test`, and `data_integrity_check` all pass
  clean** - no duplication, no leakage signature in any of the 4 classes
  tested with enough rows, no missing/constant/infinite values.
- **`schema_fingerprint_check` matches no known extractor signature** -
  this is the dataset's own native format, not CICFlowMeter or NetFlow.

`attack`, the dataset's own redundant binary 0/1 target for the same rows
`category` already labels (5-class: DoS/DDoS/Reconnaissance/Normal/Theft),
is dropped via `schema.drop_columns` rather than used as the audit's label.
`subcategory` (a finer-grained version of the same `category` label) and
`pkSeqID` (a bare sequential row identifier) are dropped for the same
reason.

How the data was obtained: OpenML dataset 42072 "bot-iot-all-features",
created directly by the original dataset authors (Koroniotis, Moustafa,
Sitnikova, Turnbull), downloaded via OpenML's own direct parquet endpoint
(no authentication required). 3,668,522 rows confirmed via direct
inspection; only 477 rows are `Normal` traffic, confirmed before any check
ran.

Run on a local dev VM, audit only (`--skip-benchmark` for the scorecard
itself; a full benchmark pass was also run separately for local
validation). Produced with IDS2Eval at commit `2ae2016`.

Files: `config.yaml` (input), `audit_report_before.json` /
`audit_report_after.json` (full findings), `dataset_fingerprint.json` /
`environment.json` (provenance), `SCORECARD.html` / `scorecard.json` /
`SCORECARD.md` (the citable rollup, see
[guide/checks.md](../../guide/checks.md#the-scorecard) for the format).
No `scorecard.pdf`/`.png`: matching the other examples, this one ships the
HTML scorecard only, the same thing the dashboard shows.
