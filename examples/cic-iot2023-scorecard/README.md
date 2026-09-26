# Example: CIC-IoT2023 scorecard

A real IDS<sup>2</sup>Eval run against
[CIC-IoT2023](https://www.unb.ca/cic/datasets/iotdataset-2023.html)
(46.8M flows, 34 fine-grained attack labels across 8 coarser
categories) - not a synthetic fixture. A uniform 500K-row reservoir
sample, split 80/20 at random. Produced with `config.yaml` in this
folder; see [SCORECARD.md](SCORECARD.md) for the full result, or
download [SCORECARD.html](SCORECARD.html) and open it in a browser for
the styled version.

**Result: failed** - 17 of 19 checks `ok`, one `warning`
(`class_distribution_report`), one `flag`
(`feature_auc_ranking_check`, described below), after dedup.

Three things worth pointing out about what's actually in here:

- **`fin_count` alone reaches AUC 0.999 identifying `DDoS-RSTFINFlood`,
  and the flag survives dedup.** Unlike most single-feature shortcuts
  this project finds, this one isn't a leakage artifact to fix: the
  fine-grained label names the exact mechanism the feature counts (a
  flood of TCP packets with the RST+FIN flags set), so a
  near-perfect standalone AUC here is closer to a tautology than a
  discovery. It's still exactly the kind of thing
  `feature_auc_ranking_check` is supposed to surface: a reader deciding
  whether a reported accuracy reflects "the model learned attack
  behavior" needs to know when one label's ground truth is
  definitionally recoverable from one feature, whatever the cause.
- **`label_conflict_check` finds 13.58% of rows (67,916 of 500,000)
  with a feature vector mapped to more than one fine-grained label**,
  concentrated almost entirely in two coarse categories: DoS at 25.9%
  conflicting and DDoS at 12.7%, against under 0.3% for Benign, Mirai,
  and Recon. Many of CIC-IoT2023's fine-grained flood variants (TCP,
  UDP, SYN, ICMP, and so on within DoS/DDoS) are statistically
  indistinguishable from each other in this flow-level feature set,
  even though the label taxonomy treats them as separate classes.
  Every one of these conflicts resolves to 0% after `preprocessing.dedup`,
  the same duplication-not-genuine-confusion pattern this check
  shows on other datasets in this project.
- **`class_distribution_report` finds a 3030:1 majority:minority train
  ratio across 34 classes** (4394:1 before dedup), with 19 classes
  under 1% of train, the same long-tail imbalance CIC-IoT2023's own
  scale over other IoT NIDS datasets doesn't avoid.
- **The before/after dedup contrast is real**: `audit_report_before.json`
  shows 21.47% train duplication and 31.61% of test rows leaking a
  train feature-match; after `preprocessing.dedup`, `audit_report_after.json`
  shows 0% for both. `dedup_check`'s per-class breakdown names which
  categories carry it: DDoS at 24.8% train duplication and DoS at
  20.4%, against under 0.2% for Benign, Mirai, and Recon, the same two
  categories driving the label-conflict figure above.
- **`homogeneity_test` and `near_duplicate_class_check` run on the 8
  coarse categories** (`schema.attack_category_column`), not the 34
  fine-grained labels, and both come back clean: no statistically
  significant leakage signature, and only 2 of 3,340 sampled rows with
  a near-zero-distance neighbor under a different coarse category.

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
