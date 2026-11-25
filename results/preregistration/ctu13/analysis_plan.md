# CTU-13 external audit: analysis plan

This plan, the three configurations beside it, `validation/ctu13_prepare.py`
and `validation/ctu13_independent_check.py` were committed before any CTU-13
file was downloaded. The code is the tag `revision-method-freeze`; the audits
run that code unchanged. CTU-13 played no part in developing
IDS<sup>2</sup>Eval. The scripts were tested only on fabricated files with the
same columns.

## Question

Does the frozen framework, run on a real benchmark it was not developed on,
(1) run from a configuration alone, (2) report diagnostics that an independent
recomputation confirms, and (3) detect a shortcut whose existence is known from
the dataset's own documentation rather than from IDS<sup>2</sup>Eval?

## Data

- CTU-13 (Garcia, Grill, Stiborek and Zunino, 2014, Computers & Security 45,
  100-123, doi:10.1016/j.cose.2014.05.011), the owners' bidirectional NetFlow
  files, one per scenario, 13 scenarios. The owners advise against the
  unidirectional NetFlows, which are not used.
- Prepared by `validation/ctu13_prepare.py` (label rule fixed there): botnet if
  the owners' label contains "Botnet", else normal if it contains "Normal",
  else excluded as background, whose ground truth is unknown. The preparation
  manifest records each input file's SHA-256 and the rows per scenario and
  label.
- Label: botnet versus normal. Attack category: the scenario's botnet family.
- Features: the NetFlow fields (duration, protocol, direction, state, type of
  service, packet and byte counts) and the identifier columns (source and
  destination address and port), which stay in the feature set as they do for
  the development datasets. Start time and scenario are excluded from the
  features; start time feeds the temporal checks and scenario the scenario
  checks.

## Runs

One audit per grouping key, identical otherwise:

| Config | Grouping key |
|---|---|
| `ctu13-5tuple.yaml` | source address, source port, destination address, destination port, protocol |
| `ctu13-coarse.yaml` | source address, destination address, destination port, protocol |
| `ctu13-host.yaml` | source address |

Each runs the default checks plus `resplit_falsification`,
`repeated_seed_falsification_check` (10 seeds), `result_robustness_check`,
`reuse_removal_falsification`, `scenario_holdout_falsification`,
`cross_capture_matrix_check` and `known_issue_lookup`, on a random 80/20 split,
before and after deduplication as the command line does. Materiality: the
defaults, 0.01 for accuracy, balanced accuracy and macro-F1, every metric
deciding the status. `homogeneity_test` reports the cluster interval by source
address next to its default interval, which decides.

Known in advance: `cross_capture_matrix_check` caps at six scenarios and will
report that it skipped CTU-13's thirteen. It is left enabled so the scorecard
shows this.

## Expectations

Stated from the dataset's documentation, before any data was seen. They are
not success criteria for the framework; each is reported as met or not.

- E1, identifier shortcut. The owners assigned botnet labels to flows from and
  to the known infected hosts, so host addresses determine the label by
  construction. Expected: `identity_column_flag` flags the address columns, and
  removing the identifier columns changes the score in
  `result_robustness_check`.
- E2, key granularity. Source ports are mostly ephemeral, so the 5-tuple key
  should put most rows in single-row groups; the coarse and host keys should
  form far fewer groups.
- E3, host dependence. Each scenario's botnet traffic comes from one to ten
  infected hosts. Expected: the host-grouped split removes most of a family's
  training rows when its hosts fall in test, and scores materially lower than
  the random split, with the class-support loss reported as the likely cause
  (the pattern seen on ToN-IoT).
- E4, 5-tuple grouping. Expected: no material change, because the key is near
  unique (E2), which makes this result uninformative rather than reassuring.

## Success criteria for the framework

- S1, operability: the three audits complete from the configurations above with
  no change to the code.
- S2, diagnostic agreement: duplicate counts, the number of test rows reusing a
  training feature vector, and each key's group count and singleton share are
  recomputed by `validation/ctu13_independent_check.py`, which does not import
  IDS<sup>2</sup>Eval (pandas, and scikit-learn's `train_test_split` to rebuild
  the same split), and must match the audit exactly.
- S3, known-shortcut detection: E1 is detected (the address columns flagged, and
  an identifier effect reported with its per-metric verdict).

## Reporting and deviations

Every finding of every run is reported, including checks that misfire, skip or
are inconclusive. A code change after the data is seen is a deviation: it is
reported with its reason, and results are shown both before and after it. No
threshold, key, label rule or feature choice changes after the data is seen.

## Compute

A single machine or a Kaggle CPU session; the prepared file is expected to be
about a million rows once background flows are excluded.
