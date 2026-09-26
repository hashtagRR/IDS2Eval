# Example: UNSW-NB15 scorecard

A real IDS<sup>2</sup>Eval run against the official, pre-split
[UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
CSVs - not a synthetic fixture. Produced with `config.yaml` in this
folder; see [SCORECARD.md](SCORECARD.md) for the full result, or
download [SCORECARD.html](SCORECARD.html) and open it in a browser for
the styled version.

**Result: passed with warnings** - 12 of 13 checks `ok`, one `warning`
(`known_issue_lookup`, described below), zero flags.

Three things worth pointing out about what's actually in here:

- **`known_issue_lookup` correctly caught a real file-naming inversion.**
  This redistribution's `UNSW_NB15_testing-set.csv` has 175,341 rows and
  `UNSW_NB15_training-set.csv` has 82,332 - swapped relative to the
  dataset's documented train/test convention. `config.yaml` corrects for
  it (see its comments); the warning is the curated table surfacing that
  this is a known issue worth checking for regardless.
- **`near_duplicate_class_check` finds 472 of 4,630 sampled rows (10.19%)
  with a near-zero-distance neighbor under a different label before
  dedup**, `Backdoor`/`DoS` and `Analysis`/`DoS` the most affected pairs;
  after dedup, none remain across the 10 classes tested, the same
  duplication-not-genuine-confusion pattern `label_conflict_check` shows
  on other datasets in this project.
- **`leakage_screen`'s top feature is `sttl`** - independently reproducing
  the published TTL-topology bias in UNSW-NB15 referenced in the main
  [guide/checks.md](../../guide/checks.md).
- **`one_rule_check` finds `sttl <= 61` alone reaches 68.0% test accuracy**
  (88.1% train) - the same feature `leakage_screen` flags, now as a literal
  rule; `label_conflict_check` and `temporal_leakage_check` both pass (no
  feature vector maps to more than one label, and there's no
  `schema.timestamp_column` configured for this dataset).
- **The before/after dedup contrast is real**: `audit_report_before.json`
  shows 42.38% train duplication; after `preprocessing.dedup`,
  `audit_report_after.json` shows 0%, and the train-class imbalance ratio
  shifts from 2:1 to roughly 1:1 - the duplicates were disproportionately
  one class.

Re-run 2026-09-26 to pick up `near_duplicate_class_check`, which is why
the check count reads 13; the verdict and every other finding are
unchanged from the original run.

Files: `config.yaml` (input), `audit_report_before.json` /
`audit_report_after.json` (full findings), `dataset_fingerprint.json` /
`environment.json` (provenance), `SCORECARD.html` / `scorecard.json` /
`SCORECARD.md` (the citable rollup, see
[guide/checks.md](../../guide/checks.md#the-scorecard) for the format).
No `scorecard.pdf`/`.png`: that chart predates the current scorecard
format and hasn't been updated to match it (it still lumps
`known_issue_lookup` in with the other checks and shows no raw/cleaned
comparison), so this example matches the other examples and ships the
HTML scorecard only, the same thing the dashboard shows.
