# Example: CIC-IDS2017 scorecard

A real IDS<sup>2</sup>Eval audit of [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html)'s
`MachineLearningCSV` release - all 8 day-files, all 2,830,743 flows, loaded in full
(no sampling) and split 80/20 at random, stratified by label. Produced with
`config.yaml` in this folder; open [SCORECARD.html](SCORECARD.html) in a browser for
the full result, or read [SCORECARD.md](SCORECARD.md).

**Result: failed** - 6 ok, 4 warnings, 3 flags after dedup, across 13 checks.

What it found:

- **`near_duplicate_class_check` finds 2 of 6,029 sampled rows (0.03%) with a
  near-zero-distance neighbor under a different label**, both `DoS Slowhttptest` /
  `DoS slowloris`, unchanged after dedup. A tiny share, but the same pattern
  `label_conflict_check` finds at much larger scale below: two labels that are
  hard to tell apart from features alone.
- **`label_conflict_check` finds 719 feature vectors (7,144 rows, 0.25%) mapped to
  more than one label, before dedup**; 335 of these span train and test, so a row's
  label there depends on which copy happened to land where.
- **`one_rule_check` finds `Bwd Packet Length Std <= 1495` alone reaches 85.6% test
  accuracy** (85.6% train), below the 95% flag threshold.
- **`Destination Port` alone predicts the label at AUC 0.929** (`identity_column_flag`),
  reproducing the published finding that destination port is a severe shortcut
  feature across the CIC family (Flood et al. 2024), the same one this tool found
  on CIC-IDS2018.
- **Heavy duplication**: 247,799 train rows (10.94%) are duplicates, and 81,604 test
  rows (14.41%) exactly match a train row - scores on those measure memorization.
- **Known CIC-IDS2017 data defects**, all caught by `data_integrity_check`: 8 constant
  features (`Bwd PSH Flags`, `Bwd URG Flags`, and all six `*Bulk*` features), ±inf in
  `Flow Bytes/s` and `Flow Packets/s`, and missing values in `Flow Bytes/s`.
- **CICFlowMeter signature matched** (`schema_fingerprint_check`): early CICFlowMeter
  releases miscalculated ~34 features (Engelen et al. 2021; Rosay et al. 2021) -
  check the extractor version before trusting rate/duration features.
- **`homogeneity_test` flags `DoS Slowhttptest`** at p=0.0056 (and `Bot` on the raw data).
  Treat this one as weak: 12 classes are each tested at p<0.05 with no
  multiple-comparison correction, so about one false positive is expected by
  chance, and a Bonferroni cutoff (≈0.004) would not flag it.
- **Imbalance of 185,530:1**, with 11 of 15 classes under 1% of train.
- **`known_issue_lookup` now carries two curated entries for this dataset**: the
  traffic capture itself has packet misorder and duplication, with some launched
  attacks left unlabeled in the released CSVs (Engelen et al. 2021), and an
  independent re-labeling audit measured 6.67% overall label corruption, some
  classes above 75%, with Heartbleed at only 11 rows (0.022% of the dataset), too
  few to evaluate reliably regardless of labeling accuracy (Cantone et al. 2024).

How the data was obtained: the 8 `MachineLearningCSV` files from a Hugging Face
mirror (`c01dsnap/CIC-IDS2017`), downloaded 2026-09-24; every file's SHA-256 matched
the mirror's published checksum. The official UNB download link returned an HTML
page rather than the archive. In this copy the Web Attack labels carry a Unicode
replacement character (`Web Attack � Brute Force`) where the original has an
invalid byte - the labels are otherwise unchanged.

Run on a 4-vCPU VM, audit only (`--skip-benchmark`). Produced with IDS2Eval at
commit 7834a67.
