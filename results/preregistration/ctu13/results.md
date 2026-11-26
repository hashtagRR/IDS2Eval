# CTU-13 external audit: results against the analysis plan

Runs: `runs/5tuple`, `runs/coarse`, `runs/host` (one audit each, Kaggle CPU sessions, code at commit
efe22d5, whose package is identical to tag `revision-method-freeze`). Data: the owners' archive
(SHA-256 in `archive.sha256`) prepared by `validation/ctu13_prepare.py`; the prepared file's
uncompressed SHA-256 (`ctu13_labelled.csv.sha256`) was checked in every run. Preparation manifest:
`ctu13_labelled.manifest.json`. No deviation from the plan: no code, configuration, label rule or
threshold changed after the data was seen.

Prepared data: 801,132 flows, 444,699 botnet and 356,433 normal; 19,175,568 background flows excluded.

## Success criteria

| Criterion | Outcome |
|---|---|
| S1, operability | Met. All three audits completed from their configurations with no code change (exit 0). |
| S2, diagnostic agreement | Met. `validation/ctu13_independent_check.py` matched every audit exactly: 6,508 training duplicates, 2,675 test rows reusing a training vector, 256 test-internal duplicates, and each key's group count and single-row-group share. |
| S3, known-shortcut detection | Met. `identity_column_flag` flags the address columns in every run (source address: standalone AUC 1.0 over 58 hosts); a single rule on the source address reaches 88.3% accuracy; removing the identifier columns costs 3.4 points of accuracy, balanced accuracy and macro-F1 (`result_robustness_check`, whose 8-point warning tier this spread does not reach). |

## Expectations

| Expectation | Outcome |
|---|---|
| E1, identifier shortcut | Met (see S3). The port-and-protocol and timestamp checks also flag. |
| E2, key granularity | Met. Rows in single-row groups: 52.7% under the 5-tuple (490,950 groups), 7.3% under the coarse key (74,076 groups), none under the source host (60 groups; the largest holds 32.8% of rows). |
| E3, host dependence | Met. Ten-seed grouped resplit by source host: accuracy drop 0.308 [0.058, 0.558], balanced accuracy 0.289 [0.080, 0.497], macro-F1 0.509 [0.287, 0.730], all material; per-seed drops range from 0 to 0.98, as whole infected hosts, and with them most of a family's training rows, fall on one side. The coarse key behaves similarly (balanced accuracy drop 0.193 [0.038, 0.349]). |
| E4, 5-tuple grouping | Met. No material change on any metric (accuracy drop 0.0009 [-0.0004, 0.0023]), with half the rows in single-row groups: uninformative, as expected. |

## Other findings

- `cross_capture_matrix_check` skipped, as stated in the plan (13 scenarios, cap 6).
- `scenario_holdout_falsification` held out scenario 7 (the smallest, 1,740 flows): no material change.
- `reuse_removal_falsification`: removing the 4,585 training rows that share a vector with a test row changes no metric materially.
- `homogeneity_test`: inconclusive for the normal class in every run; no class shows excess matching.
- `temporal_realism_check` flags: the Sogou family covers 0.1% of the capture window.

## Addendum (written after the audit)

E3 predicted both a material host-grouped drop and its cause, the loss of a family's training rows when its hosts fall in test. The drop was met. The cause was not measured: the frozen code predates the class-support reporting added later, so E3 is reported in the paper as partly met. Nothing in the audit, its configuration or its outputs changed.
