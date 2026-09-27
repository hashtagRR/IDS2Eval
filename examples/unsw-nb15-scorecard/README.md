# Example: UNSW-NB15 scorecard

A real IDS<sup>2</sup>Eval run against the official, pre-split
[UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
CSVs - not a synthetic fixture. Produced with `config.yaml` in this
folder; see [SCORECARD.md](SCORECARD.md) for the full result, or
download [SCORECARD.html](SCORECARD.html) and open it in a browser for
the styled version.

**Result: failed** - 17 of 19 checks `ok`, one `warning`
(`known_issue_lookup`), one `flag` (`row_order_leakage_check`, below).

Three things worth pointing out about what's actually in here:

- **`row_order_leakage_check` flags the test split as essentially fully
  block-ordered by label** (contiguity ratio 0.0002, versus what a
  shuffled ordering of the same labels would produce), unchanged after
  dedup. This redistribution's test file wasn't shuffled before being
  split off: rows for one attack class sit together in long runs
  rather than interleaved with other classes, so anything downstream
  that happens to be sensitive to row order (a naive time-series split,
  a batch-boundary artifact in some training loops) inherits that
  structure. Train is much closer to what shuffling would produce
  (0.09) but still measurably below 1.0.
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
  rule; `feature_auc_ranking_check` corroborates it a third way, `sttl`
  alone reaches AUC 0.872 (0.881 before dedup), below the 0.95 flag
  threshold; `label_conflict_check` and `temporal_leakage_check` both
  pass (no feature vector maps to more than one label, and there's no
  `schema.timestamp_column` configured for this dataset).
- **The before/after dedup contrast is real**: `audit_report_before.json`
  shows 42.38% train duplication; after `preprocessing.dedup`,
  `audit_report_after.json` shows 0%, and the train-class imbalance ratio
  shifts from 2:1 to roughly 1:1 - the duplicates were disproportionately
  one class.
- **`dedup_check`'s per-class breakdown names that class**: `Generic` sits
  at 90.19% train duplication, `Normal` at 7.47%, both folded into the one
  42.38% global figure above. A per-class rate this uneven means the
  global number describes almost nobody's actual duplication rate.

Re-run 2026-09-27 to pick up `row_order_leakage_check`, `feature_auc_ranking_check`,
and `temporal_realism_check` (the last one no-ops here, no `schema.timestamp_column`
configured), which is why the check count reads 19 and the verdict changed from
`passed_with_warnings` to `failed` - a genuinely new finding
(`row_order_leakage_check`'s test-split block-ordering above), not a change in
any pre-existing result. An earlier re-run (2026-09-26) had already added
`near_duplicate_class_check` and a per-class breakdown on `dedup_check`,
`label_conflict_check`, `leakage_screen`, and `identity_column_flag`
(`details["by_class"]` in the JSON reports); every finding from both re-runs
not mentioned above is unchanged from the original run.

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
