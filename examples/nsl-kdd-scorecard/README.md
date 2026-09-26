# Example: NSL-KDD scorecard

A real IDS<sup>2</sup>Eval audit of [NSL-KDD](https://www.unb.ca/cic/datasets/nsl.html)'s
official `KDDTrain+` / `KDDTest+` partition (125,973 / 22,544 rows). Produced with
`config.yaml` in this folder; open [SCORECARD.html](SCORECARD.html) in a browser for
the full result, or read [SCORECARD.md](SCORECARD.md).

**Result: failed** - 14 ok, 3 warnings, 2 flags after dedup, across 19 checks.

What it found:

- **`feature_auc_ranking_check` finds `wrong_fragment` alone reaches AUC 1.000
  identifying `teardrop`**, and the flag survives dedup. Not a leakage artifact
  to fix: `teardrop` is a fragmentation attack, defined by sending overlapping,
  malformed IP fragments, so a feature literally counting wrong fragments
  recovering that label perfectly is closer to a tautology than a discovery,
  the same story as `wrong_fragment`'s counterpart features in other datasets
  in this project.
- **`one_rule_check` finds `same_srv_rate <= 0.495` alone reaches 63.4% test
  accuracy** (84.0% train) - well below the 95% flag threshold, and the gap between
  train and test accuracy is itself a sign the rule doesn't generalize cleanly.
- **`label_conflict_check` flags 116 feature vectors (247 rows, 0.17%) mapping to
  more than one label on the raw data**, 58 of them spanning train and test; after
  dedup, zero conflicts remain, the same duplication-not-contradiction pattern seen
  in the CICDDoS2019 example. `temporal_leakage_check` passes: there's no
  `schema.timestamp_column` configured for this dataset.
- **`known_issue_lookup` flags NSL-KDD's own by-design novel-attack split**
  (Tavallaee et al. 2009): the 17 test-only attack types below aren't an accident
  of this partition, they're the dataset's stated purpose.
- **`homogeneity_test` flags `ipsweep` and `smurf` before dedup, but only `smurf`
  survives after** (p = 2e-8): test `smurf` rows sit systematically closer to
  train than train rows sit to each other, even with no exact duplicates left.
  `ipsweep`'s flag was entirely a duplication artifact; `smurf`'s traffic is
  highly repetitive by construction, so a model scoring well on it says little
  about generalization.
- **Extreme imbalance (33,670:1)**, with 16 attack types under 1% of train.
- **17 attack types exist only in the test set** (`apache2`, `mailbomb`, `snmpguess`,
  ...), and two (`spy`, `warezclient`) only in train - NSL-KDD's deliberate
  novel-attack design, visible in `audit_report_after.json`'s class distribution.
  Per-class scores on those types can't reflect anything the model learned.
- **`num_outbound_cmds` is constant** (always 0) - a well-known KDD'99 artifact.
- **`near_duplicate_class_check` and `row_order_leakage_check` pass**: no
  near-zero-distance feature vector spans two different labels across the 14
  classes with enough rows to test, and adjacent-row label clustering matches
  what a shuffled ordering of the same labels would produce.
- **Low duplication, as intended**: NSL-KDD was built to remove KDD'99's redundancy,
  and it shows - 16 train duplicates, and 664 test rows (2.95%) that exactly match
  a train row. Small, but still a flag before dedup: those rows test memorization.

How the data was obtained: `KDDTrain+.txt` / `KDDTest+.txt` from a GitHub mirror of
the official files, downloaded 2026-09-24. The originals have no header row, so the
standard KDD'99 column names (plus `label`, `difficulty`) were prepended at download
time; `difficulty` is dropped as annotation metadata, not a traffic feature. The
audit's `label` is the per-attack name (23 classes), not a binary normal/attack flag.

Run on a 4-vCPU / 15GB VM, audit only (`--skip-benchmark`). Re-run 2026-09-26 to
pick up `feature_auc_ranking_check`, `row_order_leakage_check`, and
`temporal_realism_check` (the last two no-op here, no `schema.timestamp_column`
configured), which is why the check count reads 19; every other finding is
unchanged from the original run. Produced with IDS2Eval at commit ad380be.
