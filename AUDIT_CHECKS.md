# The Audit Checks

Most published NIDS results are evaluated on benchmark datasets whose
quality is taken on faith, disclosed in a boilerplate limitations
paragraph, or not tested at all. These 16 checks operationalize a
systematic audit methodology as reusable, config-driven software,
rather than a one-off analysis notebook re-derived per dataset. Twelve
run by default (v1, no external data needed); four are opt-in (v2,
need a second dataset, a declared timestamp column, or heavier
compute).

Each check returns a finding: `{check, status, summary, details}`,
where `status` is `ok`, `warning`, or `flag`, a specific, checkable
signature of a real problem, not a vague heuristic score.

## v1, always on

### `dedup_check`
Exact feature-space duplicates, within and across train/test. A test
row whose *features* exactly duplicate a train row measures
memorization, not generalization, regardless of whether its label
happens to match. Run twice when `preprocessing.dedup` is on: once
before cleanup, once after, so a claim like "12% duplicate leakage
before, 0% after" is backed by two real runs, not assumed. On real
UNSW-NB15 data this found 42% train duplication and correctly dropped
to 0% after dedup.

### `label_conflict_check`
Groups rows by the same features `dedup_check` compares on, and checks
whether every row in a group shares one label. A feature vector mapped
to more than one label is a stronger claim than a duplicate: the
ground truth contradicts itself, since even a model that memorizes
every training row perfectly still can't get both instances right.
Independently motivated from three directions: Deepchecks' "Conflicting
Labels" check in general ML tooling, Northcutt et al. 2021's finding
that label errors average 3.3% across major ML benchmarks, and Wu &
Keogh 2021's "mislabeled ground truth" flaw in time-series anomaly
benchmarks (IEEE TKDE). Like `dedup_check`, must run on the raw data:
`preprocessing.dedup` already ignores the label column when grouping
duplicates, so it collapses a conflicting group to one arbitrarily-kept
row before this check ever sees it, and will always report zero after
cleaning.

### `leakage_screen`
Fits a fast RandomForest and inspects its own `feature_importances_`
rather than guessing candidate leakage columns from domain knowledge.
A single feature or pair carrying a large majority of total split
importance is a specific, checkable signature of shortcut learning.
This is the same method that independently reproduces Flood et al.
2024's (IEEE EuroS&P, Distinguished Paper) finding that `Destination
Port` alone hits near-perfect accuracy
across the entire CIC family, UNSW-NB15, CIDDS, CTU-13, and NSL-KDD,
confirmed independently against the real, official CIC-IDS2018
distribution in this project's own validation.

### `one_rule_check`
Fits a single depth-1 decision tree, one feature, one threshold, and
reports the winning rule in plain language rather than an abstract
importance share. Per Wu & Keogh 2021 (IEEE TKDE): most widely-used
time-series anomaly benchmarks turned out solvable by a single line of
code, which meant published algorithm comparisons on them measured
nothing. A depth-1 tree is exactly a brute-force search over every
feature and threshold for the single best split, done in one cheap fit.

### `identity_column_flag` / `low_cardinality_warning`
Standalone predictive power and cardinality of IP/port/MAC-pattern
columns you declare via `schema.id_like_columns`. Per Sarhan, Layeghy
& Portmann 2022 (*Mobile Networks and Applications*: the NetFlow-
standard feature set drops these columns for exactly this reason) and
Kostas et al. 2024/2025 ([arXiv:2406.07578](https://arxiv.org/abs/2406.07578):
packet-level IP/port models hit near-100% in-dataset, lose over 90%
cross-dataset). Low cardinality specifically generalizes Meidan et al.
2018's ([arXiv:1805.03409](https://arxiv.org/abs/1805.03409)) N-BaIoT
per-device overfitting finding to any dataset with a limited
attacker/victim IP pool.

### `temporal_leakage_check`
How well `schema.timestamp_column` alone predicts the label, as a
standalone ROC AUC, the same method as `identity_column_flag` applied
to time. Datasets collected as scenario-specific time windows (attack
X launched 2-3pm, attack Y 3-4pm, ...) let a model win by learning
"when," not "what," which Wu & Keogh 2021 call "run-to-failure bias"
in time-series anomaly benchmarks. Confirmed on this project's own
CIC-IDS2018 run: a RandomForest given nothing but the Timestamp column
reached AUC 0.93 predicting benign vs. attack. No-ops (reports `ok`)
unless `schema.timestamp_column` is set, since there's no universal
column name to detect automatically.

### `homogeneity_test`
The methodological centerpiece for distinguishing real leakage from
inherent class homogeneity. For each class, computes each test row's
nearest-neighbor distance to the training set, and, critically, the
*same statistic as a control*: each training row's nearest-neighbor
distance to the rest of the training set, excluding itself. If the two
are statistically indistinguishable (Mann-Whitney U), the near-
duplication is a property of the class population itself, not an
artifact of the split.

### `resplit_falsification`
The nearest-neighbor test's one blind spot: a random split can't
distinguish "this class is inherently homogeneous" from "a different
split would reveal real difficulty." Breaking that symmetry requires
an actual intervention: a session/time-grouped split
(`StratifiedGroupKFold` over `dataset.group_columns`) that makes
session-correlated leakage structurally impossible, then comparing
accuracy directly. Applied to the real, independently-reproduced
CIC-IDS2018 near-saturation-accuracy question: a grouped resplit
reproduced the random split's accuracy to within 0.003 percentage
points, settling the question by direct experiment rather than a
disclosed-but-untested caveat.

### `class_distribution_report`
Per-class counts, shares, and imbalance ratio, the universal pattern
across NIDS benchmarks (KDD99's U2R/R2L under 1-2%, BoT-IoT's 0.01%
benign, TON_IoT's 3.56% benign). On real UNSW-NB15 data, comparing this
check's before/after-dedup output surfaced a genuine finding: the
imbalance ratio shifted from 2:1 to roughly 1:1 after deduplication.
Duplicated rows were disproportionately one class.

### `schema_fingerprint_check`
Matches known feature-*extractor* signatures (currently CICFlowMeter)
by column-name fingerprint, regardless of which dataset the columns
came from, and surfaces that extractor's documented bugs. Per Rosay
et al. 2021 (34 miscalculated features in early CICFlowMeter releases,
which motivated the corrected LYCOS-IDS2017 redistribution).

### `data_integrity_check`
Missing label values, missing or constant/near-constant feature
columns, and plus-or-minus-infinity values: the complement of
`leakage_screen`, catching features carrying too *little* signal, or
garbage values, rather than too much. (Infinity is not a hypothetical
here: CIC-IDS2018's rate features like `Flow Byts/s` are literally
`Infinity` when flow duration is zero.)

## v2, opt-in, need `audit.reference_dataset` or heavier compute

### `synthetic_realism_check`
Trains a domain classifier to distinguish this dataset's rows from a
reference real-traffic sample. High separability is a specific,
checkable signature of distributional divergence, beyond simply "two
datasets differ." Per Layeghy, Gallagher & Portmann 2021 and Catillo,
Pecchia & Villano 2021 (ACISP/Springer) on synthetic-vs-real benign
traffic divergence producing unrepresentative near-perfect results.

### `cross_dataset_drift_check`
Trains on this dataset, evaluates on `reference_dataset` in a unified
feature space; a material accuracy drop is evidence the model learned
dataset-specific artifacts rather than generalizable attack behavior.

### `known_issue_lookup`
A curated table of documented per-dataset problems, matched on
`dataset.name`, currently seeded with CIC-IDS2018's 2018-02-23
Brute-Force-Web mislabeling (Liu et al. 2022, IEEE CNS) and UNSW-NB15's
train/test file-naming inversion (independently verified in this
project's own methodology: some redistributions' file names are
swapped relative to the documented row-count convention). Needs no
reference dataset. This is curation work, not a new algorithm. The
table is deliberately small so far, and growing it is a good place for
contributors to help, including judgment calls like whether an older,
largely superseded dataset (KDD99 being the obvious case: still widely
cited, but generally considered deprecated by the research community)
is worth an entry at all.

### `seed_sensitivity_check`
Re-fits `leakage_screen` and `one_rule_check` across 5 seeds (0-4) and
checks whether their flag/ok conclusion holds up across seeds, rather
than trusting the point estimate a single seed happened to produce.
Per D'Amour et al. 2022 (JMLR, "Underspecification Presents Challenges
for Credibility in Modern Machine Learning"): predictors with identical
training-domain performance can behave very differently under stress
tests, purely from seed choice. Opt-in rather than v1 since it refits
two classifiers per seed on top of the single-seed runs those checks
already do, meaningful extra compute on a large dataset.

## The scorecard

Every run that audits a dataset also writes `SCORECARD.html`,
`SCORECARD.md` and `scorecard.json`: a citable rollup of the findings
above plus the dataset fingerprint and tool version already computed
elsewhere, not a new check itself. The goal is a single artifact a
paper can point to instead of "this dataset's quality was not
independently verified": *"this result was obtained on a dataset that
passed the following IDS2Eval checks."*

**Pass/fail is an explicit, fixed rule**, since it becomes a citable
claim: any `flag` gives `failed`; no flags but any `warning` gives
`passed_with_warnings`; all `ok` gives `passed`. The scorecard reflects
whichever audit pass describes the data actually shipped in the run,
after dedup if `preprocessing.dedup` ran, otherwise the only pass there
was.

**Two sections: checks and known issues.** Every enabled check is
sorted into one of two tables, by whether its result depends on this
run's actual data or not:

- **Checks**: everything that measures the loaded data and could, in
  principle, be reacted to (drop a column, resample, switch
  `dataset.split_mode`, or just note the caveat). This is where
  `dedup_check`, `label_conflict_check`, `leakage_screen`,
  `one_rule_check`, `identity_column_flag`, `temporal_leakage_check`,
  `homogeneity_test`, `class_distribution_report`,
  `low_cardinality_warning`, `data_integrity_check`,
  `resplit_falsification`, `synthetic_realism_check`,
  `cross_dataset_drift_check` and `seed_sensitivity_check` live.
- **Known issues**: `known_issue_lookup` and `schema_fingerprint_check`.
  Both report a documented, curated fact (a published labelling error,
  a known-buggy extractor) rather than a measurement of this run's
  data, and nothing in this run's config can fix what they report. So
  they get their own section, with a single Status column, rather than
  being mixed into the checks table with a "raw/cleaned" split that
  would only invite the question of why cleaning the data didn't
  change them. (`resplit_falsification` looks similarly "structural":
  its result also can't move with dedup, since it reloads the raw data
  itself, but it stays in the checks table, because it genuinely
  measures this run's split methodology, and switching to a grouped
  split is a real fix. See `ids2eval.audit.KNOWN_ISSUE_CHECKS` vs
  `STRUCTURAL_CHECKS`.)

Both tables number their rows starting at 1.

**Raw and cleaned data, side by side.** Within the Checks table, every
check runs twice: on the raw data as loaded, and on the cleaned data,
the same data with exact duplicate rows removed (`preprocessing.dedup`);
nothing else changes between the two runs. Each check gets one row with
a status column for each pass, so a problem that duplicates caused (say
`dedup_check` going from `flag` to `pass`) reads straight across its
row, and rows whose status differs are highlighted. The summary is the
cleaned-data one, with the raw-data summary underneath whenever the
numbers moved (UNSW-NB15's `class_distribution_report` staying `ok`
while its imbalance ratio goes from 2:1 to 1:1). `resplit_falsification`'s
result can't differ between the two passes (see above), so it gets a
single status spanning both columns instead of two identical badges.
With dedup off there's only the raw-data run, and one Status column
throughout. Row counts before and after cleaning are reported
alongside ("What cleaning changed"). The verdict itself is still
judged on the final pass only: a problem dedup already removed isn't a
problem with the data the run shipped.

A `scorecard_schema_version` field (independent of `ids2eval`'s own
package version) means a citation naming a schema version stays
parseable even after the tool itself moves on. The scorecard's shape
is a stability commitment in a way an internal output format isn't.
Schema 1.1 is additive over 1.0: it adds `counts`, `checks` (one
entry per check, `{check, category, before, after}`, where `category`
is `"audit"` or `"known_issue"`, each side `{status, summary}` or `null`,
`after` is `null` throughout when dedup didn't run) and `dedup_effect`,
and leaves every 1.0 key unchanged. `findings` is still the final pass.

**A visual scorecard is opt-in** (`output.write_scorecard_plot`, off by
default, see [CONFIGURATION.md](CONFIGURATION.md#rendering-the-scorecard-as-a-chart)),
producing both `scorecard.pdf` and `scorecard.png` from one figure: the
pass/fail verdict, the full per-check breakdown (name, status, and the
check's own summary for this run, since a bare "8 ok, 1 warning" count
means nothing without seeing which checks and why), and, only when
those specific checks ran, a train-vs-test class distribution chart and
a horizontal bar chart of `leakage_screen`'s top feature importances (a
dominant bar *is* the leakage signature this file already describes in
prose). PDF is the deliberate primary format here, not PNG: publication
guidance (Enago's journal-figure-format guide; CASRAI's
scientific-figure rules) is consistent that vector formats are what's
actually recommended for charts and graphs, since they stay sharp at
any print size, while raster formats like PNG are meant for
photographs. PNG is generated anyway, for one practical reason vector
format can't cover: PDFs don't render inline in GitHub's Markdown
preview, so `SCORECARD.md` embeds the PNG (at a fixed display width,
not GitHub's default full native size, since this figure is tall) to
show the chart when skimmed on GitHub, while `scorecard.pdf` stays the
one to actually cite or drop into a paper's figures. Needs `matplotlib`
(`pip install "ids2eval[plots]"`), an optional extra, not a core
dependency, so turning this on is a deliberate choice, not something a
run does silently.

**Why this, and not an existing format.** Generic dataset-documentation
templates, Datasheets for Datasets
([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and Google's
Data Cards, are manual, narrative forms an author fills in, not
something a tool generates from actual checks. Generic automated
data-quality tools (Great Expectations, whylogs, TFDV) run real checks
and produce a report, but are generic-tabular, not IDS-aware or
citation-shaped. The closest NIDS-specific prior art is Flood et al.
2024's own audit heuristics (already the basis for `leakage_screen`
above), but a 2025 survey of NIDS datasets ("Network Intrusion
Datasets: A Survey, Limitations, and Recommendations",
[arXiv:2502.06688](https://arxiv.org/abs/2502.06688)) describes current
validation as still "heavily reliant on manual analysis" and calls for
more formalized, automated methodologies. This scorecard is a direct
answer to that gap, not a reinvention of something that already
existed. The scorecard/verdict framing itself draws on "Scorecards for
Synthetic Medical Data Evaluation and Reporting"
([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)), which uses the
same structural idea in a different data domain.

## What's *not* an audit finding

Structural problems severe enough to make the dataset unusable,
duplicate column names, a train/test schema sharing no feature
columns, an empty split, aren't findings at all. They raise
immediately via `dataset.validate_loaded()`, before caching or
auditing even start, because there's no meaningful "warning" to give:
nothing downstream would produce a result worth reading.
