# The Audit Checks

Most published NIDS results are evaluated on benchmark datasets whose
quality is taken on faith, disclosed in a boilerplate limitations
paragraph, or not tested at all. These 12 checks operationalize a
systematic audit methodology as reusable, config-driven software,
rather than a one-off analysis notebook re-derived per dataset. Nine
run by default (v1 — no external data needed); three are opt-in (v2 —
need a second dataset or heavier compute).

Each check returns a finding: `{check, status, summary, details}`,
where `status` is `ok`, `warning`, or `flag` — a specific, checkable
signature of a real problem, not a vague heuristic score.

## v1 — always on

### `dedup_check`
Exact feature-space duplicates, within and across train/test — a test
row whose *features* exactly duplicate a train row measures
memorization, not generalization, regardless of whether its label
happens to match. Run twice when `preprocessing.dedup` is on: once
before cleanup, once after, so a claim like "12% duplicate leakage
before, 0% after" is backed by two real runs, not assumed. On real
UNSW-NB15 data this found 42% train duplication and correctly dropped
to 0% after dedup.

### `leakage_screen`
Fits a fast RandomForest and inspects its own `feature_importances_`
rather than guessing candidate leakage columns from domain knowledge —
a single feature or pair carrying a large majority of total split
importance is a specific, checkable signature of shortcut learning.
This is the same method that independently reproduces Flood et al.
2024's (IEEE EuroS&P, Distinguished Paper) finding that `Destination
Port` alone hits near-perfect accuracy
across the entire CIC family, UNSW-NB15, CIDDS, CTU-13, and NSL-KDD —
confirmed independently against the real, official CIC-IDS2018
distribution in this project's own validation.

### `identity_column_flag` / `low_cardinality_warning`
Standalone predictive power and cardinality of IP/port/MAC-pattern
columns you declare via `schema.id_like_columns` — per Sarhan, Layeghy
& Portmann 2022 (*Mobile Networks and Applications* — the NetFlow-
standard feature set drops these columns for exactly this reason) and
Kostas et al. 2024/2025 ([arXiv:2406.07578](https://arxiv.org/abs/2406.07578) —
packet-level IP/port models hit near-100% in-dataset, lose over 90%
cross-dataset). Low cardinality specifically generalizes Meidan et al.
2018's ([arXiv:1805.03409](https://arxiv.org/abs/1805.03409)) N-BaIoT
per-device overfitting finding to any dataset with a limited
attacker/victim IP pool.

### `homogeneity_test`
The methodological centerpiece for distinguishing real leakage from
inherent class homogeneity. For each class, computes each test row's
nearest-neighbor distance to the training set, and — critically — the
*same statistic as a control*: each training row's nearest-neighbor
distance to the rest of the training set, excluding itself. If the two
are statistically indistinguishable (Mann-Whitney U), the near-
duplication is a property of the class population itself, not an
artifact of the split.

### `resplit_falsification`
The nearest-neighbor test's one blind spot: a random split can't
distinguish "this class is inherently homogeneous" from "a different
split would reveal real difficulty." Breaking that symmetry requires
an actual intervention — a session/time-grouped split
(`StratifiedGroupKFold` over `dataset.group_columns`) that makes
session-correlated leakage structurally impossible, then comparing
accuracy directly. Applied to the real, independently-reproduced
CIC-IDS2018 near-saturation-accuracy question: a grouped resplit
reproduced the random split's accuracy to within 0.003 percentage
points, settling the question by direct experiment rather than a
disclosed-but-untested caveat.

### `class_distribution_report`
Per-class counts, shares, and imbalance ratio — the universal pattern
across NIDS benchmarks (KDD99's U2R/R2L under 1–2%, BoT-IoT's 0.01%
benign, TON_IoT's 3.56% benign). On real UNSW-NB15 data, comparing this
check's before/after-dedup output surfaced a genuine finding: the
imbalance ratio shifted from 2:1 to roughly 1:1 after deduplication —
duplicated rows were disproportionately one class.

### `schema_fingerprint_check`
Matches known feature-*extractor* signatures (currently CICFlowMeter)
by column-name fingerprint, regardless of which dataset the columns
came from, and surfaces that extractor's documented bugs — per Rosay
et al. 2021 (34 miscalculated features in early CICFlowMeter releases,
which motivated the corrected LYCOS-IDS2017 redistribution).

### `data_integrity_check`
Missing label values, missing or constant/near-constant feature
columns, and ±infinity values — the complement of `leakage_screen`:
features carrying too *little* signal, or garbage values, rather than
too much. (Infinity is not a hypothetical here: CIC-IDS2018's rate
features like `Flow Byts/s` are literally `Infinity` when flow
duration is zero.)

## v2 — opt-in, need `audit.reference_dataset` or heavier compute

### `synthetic_realism_check`
Trains a domain classifier to distinguish this dataset's rows from a
reference real-traffic sample — high separability is a specific,
checkable signature of distributional divergence, not just "two
datasets differ." Per Layeghy, Gallagher & Portmann 2021 and Catillo,
Pecchia & Villano 2021 (ACISP/Springer) on synthetic-vs-real benign
traffic divergence producing unrepresentative near-perfect results.

### `cross_dataset_drift_check`
Trains on this dataset, evaluates on `reference_dataset` in a unified
feature space; a material accuracy drop is evidence the model learned
dataset-specific artifacts rather than generalizable attack behavior.

### `known_issue_lookup`
A curated table of documented per-dataset problems, matched on
`dataset.name` — currently seeded with CIC-IDS2018's 2018-02-23
Brute-Force-Web mislabeling (Liu et al. 2022, IEEE CNS) and UNSW-NB15's
train/test file-naming inversion (independently verified in this
project's own methodology — some redistributions' file names are
swapped relative to the documented row-count convention). Needs no
reference dataset — this is curation work, not a new algorithm. The
table is deliberately small so far, and growing it is a good place for
contributors to help — including judgment calls like whether an older,
largely superseded dataset (KDD99 being the obvious case: still widely
cited, but generally considered deprecated by the research community)
is worth an entry at all.

## The scorecard

Every run that audits a dataset also writes `scorecard.json` and
`SCORECARD.md` — not a new check, but a citable rollup of the findings
above plus the dataset fingerprint and tool version already computed
elsewhere. The goal is a single artifact a paper can point to instead
of "this dataset's quality was not independently verified": *"this
result was obtained on a dataset that passed the following IDS2Eval
checks."*

**Pass/fail is an explicit, fixed rule**, since it becomes a citable
claim: any `flag` → `failed`; no flags but any `warning` →
`passed_with_warnings`; all `ok` → `passed`. The scorecard reflects
whichever audit pass describes the data actually shipped in the run —
after dedup if `preprocessing.dedup` ran, otherwise the only pass there
was.

A `scorecard_schema_version` field (independent of `ids2eval`'s own
package version) means a citation naming a schema version stays
parseable even after the tool itself moves on — the scorecard's shape
is a stability commitment in a way an internal output format isn't.

**A visual scorecard is opt-in** (`output.write_scorecard_plot`, off by
default — see [CONFIGURATION.md](CONFIGURATION.md#rendering-the-scorecard-as-a-chart)),
producing both `scorecard.pdf` and `scorecard.png` from one figure: the
pass/fail verdict, the full per-check breakdown (name, status, and the
check's own summary for this run — a bare "8 ok, 1 warning" count means
nothing without seeing which checks and why), and — only when those
specific checks ran — a train-vs-test class distribution chart and a
horizontal bar chart of `leakage_screen`'s top feature importances (a
dominant bar *is* the leakage signature this file already describes in
prose). PDF is the deliberate primary format here, not PNG: publication
guidance (Enago's journal-figure-format guide; CASRAI's
scientific-figure rules) is consistent that vector formats are what's
actually recommended for charts and graphs, since they stay sharp at
any print size, while raster formats like PNG are meant for
photographs. PNG is generated anyway, for one practical reason vector
format can't cover: PDFs don't render inline in GitHub's Markdown
preview, so `SCORECARD.md` embeds the PNG (at a fixed display width,
not GitHub's default full native size — this figure is tall) to show
the chart when skimmed on GitHub, while `scorecard.pdf` stays the one
to actually cite or drop into a paper's figures. Needs `matplotlib`
(`pip install "ids2eval[plots]"`) — an optional extra, not a core
dependency, so
turning this on is a deliberate choice, not something a run does
silently.

**Why this, and not an existing format.** Generic dataset-documentation
templates — Datasheets for Datasets
([arXiv:1803.09010](https://arxiv.org/abs/1803.09010)) and Google's
Data Cards — are manual, narrative forms an author fills in, not
something a tool generates from actual checks. Generic automated
data-quality tools (Great Expectations, whylogs, TFDV) run real checks
and produce a report, but are generic-tabular, not IDS-aware or
citation-shaped. The closest NIDS-specific prior art is Flood et al.
2024's own audit heuristics (already the basis for `leakage_screen`
above), but a 2025 survey of NIDS datasets ("Network Intrusion
Datasets: A Survey, Limitations, and Recommendations",
[arXiv:2502.06688](https://arxiv.org/abs/2502.06688)) describes current
validation as still "heavily reliant on manual analysis" and calls for
more formalized, automated methodologies — this scorecard is a direct
answer to that gap, not a reinvention of something that already
existed. The scorecard/verdict framing itself draws on "Scorecards for
Synthetic Medical Data Evaluation and Reporting"
([arXiv:2406.11143](https://arxiv.org/abs/2406.11143)), which uses the
same structural idea in a different data domain.

## What's *not* an audit finding

Structural problems severe enough to make the dataset unusable —
duplicate column names, a train/test schema sharing no feature
columns, an empty split — aren't findings at all. They raise
immediately via `dataset.validate_loaded()`, before caching or
auditing even start, because there's no meaningful "warning" to give:
nothing downstream would produce a result worth reading.
