# Example: CSE-CIC-IDS2018 scorecard

A real IDS<sup>2</sup>Eval audit of [CSE-CIC-IDS2018](https://www.unb.ca/cic/datasets/ids-2018.html)'s
"Processed Traffic Data for ML Algorithms" release - all 10 day-files, 16.2M flows,
streamed from the official UNB/AWS bucket. Produced with `config.yaml` in this folder;
open [SCORECARD.html](SCORECARD.html) in a browser for the full result, or read
[SCORECARD.md](SCORECARD.md).

**Sampled, not full:** 16.2M rows don't fit in the 7.8GB VM this ran on, so the
audit covers a uniform, seeded 500K-row reservoir sample (`dataset.max_rows`), split
80/20 at random, stratified by label. Duplication rates are measured within that
sample; the full dataset's duplication is higher, since a sample only catches a
duplicate pair when both copies are drawn.

**Result: failed** - 8 ok, 3 warnings, 2 flags after dedup, across 13 checks.

What it found:

- **`near_duplicate_class_check` finds 475 of 5,317 sampled rows (8.93%) with a
  near-zero-distance neighbor under a different label before dedup**, almost all
  of them `DoS attacks-SlowHTTPTest`/`FTP-BruteForce`; after dedup, none remain
  across the 11 classes tested. The same clash `label_conflict_check` finds
  below, confirmed at the near-duplicate level rather than only exact matches.
- **`label_conflict_check` finds 882 feature vectors (15,194 rows, 3.04%) mapped to
  more than one label, before dedup.** The largest cluster is `FTP-BruteForce` and
  `DoS attacks-SlowHTTPTest`: dedup collapses `FTP-BruteForce` from 4,736 train rows
  to 17, and removes all 1,184 of its test rows as exact matches of train rows;
  looking closer, its remaining 35 distinct feature vectors all also appear labelled
  `DoS attacks-SlowHTTPTest` - identical flows, two labels. Any per-class score for
  either class is memorization of a handful of vectors, not detection. This
  reproduces Flood et al. 2024 (EuroS&P, Table 8), who report the same
  `SlowHTTPTest`/`FTP-BruteForce` clash; `FTP-BruteForce` was also launched against a
  closed port, so its flows carry almost no attack behavior.
- **`one_rule_check` finds `Fwd Seg Size Min <= 30` alone reaches 83.0% test
  accuracy** (83.2% train), below the 95% flag threshold but a reminder of how much
  of this problem a single feature explains.
- **`Dst Port` alone predicts the label at AUC 0.912** (0.925 on the raw data) -
  reproducing the published destination-port shortcut (Flood et al. 2024).
- **Heavy duplication**: 13.15% of train rows are duplicates, and 16.88% of test rows
  exactly match a train row.
- **Known data defects** (`data_integrity_check`): 8 constant features, ±inf in
  `Flow Byts/s` and `Flow Pkts/s`, missing values in `Flow Byts/s`.
- **Two curated known issues** (`known_issue_lookup`): the 2018-02-23 Brute
  Force-Web/XSS rows are ~41% mislabeled (Liu et al. 2022), and an independent
  re-labeling audit separately measured a 7.53% overall label corruption rate for
  this dataset, with some individual attack classes above 75% (Cantone et al. 2024).
- **`homogeneity_test` flags `Bot` (p=0.025) and `DoS attacks-Slowloris` (p=0.0025)**
  after dedup. Treat as weak: 9 classes are tested at p<0.05 with no multiple-comparison
  correction, and a Bonferroni cutoff (≈0.0056) keeps only Slowloris. Before dedup the
  check passed; which classes reach it at all depends on the sample.
- **Imbalance of 149,712:1**; `SQL Injection` (2 rows) and `FTP-BruteForce` (17 rows
  after dedup) end up train-only, so the test set can't measure them at all.

How the data was obtained: downloaded 2026-09-24 from the public bucket
`s3://cse-cic-ids2018/Processed Traffic Data for ML Algorithms/`; each file was
gzipped while streaming and its decompressed size checked byte-for-byte against the
bucket listing. One day-file (`Thuesday-20-02-2018`) has 4 extra columns (`Flow ID`,
`Src IP`, `Src Port`, `Dst IP`); the loader aligns it to the other files' schema.

This dataset also surfaced a crash, since fixed: a class present in train but absent
from test (here `SQL Injection`) crashed `identity_column_flag`'s AUC. Run on a
4-vCPU VM, audit only (`--skip-benchmark`). Produced with IDS2Eval at commit
7834a67.
