# IDS2Eval results

This folder holds every result behind the paper *IDS²Eval: A Falsification-Oriented Framework for Auditing Machine-Learning Intrusion Detection Benchmarks* (`~/projects/ids_audit_paper/ids_audit_paper_v0.2.md`). It has four parts:

| Folder | What it is | Size | In git |
|---|---|---|---|
| `analysis/` | JSON outputs of the validation and analysis scripts in `../validation/` | about 0.3 MB | yes |
| `logs/` | Console logs of those scripts, and the queue script that ran them | small | yes |
| `local_audit_runs/` | Full IDS2Eval audit runs made on the local VM, one folder per dataset | about 12 MB (+20 MB archives) | yes, except `archives/` |
| `batch_audit_runs/` | Full-scale audit runs made on Google Cloud Batch | about 3.5 MB | yes |

**Backup copy:** `gs://ids2eval-batch-bc67afd1/ids2eval_results/` (same layout, including `archives/`). Refresh with `gsutil -m rsync -r ~/projects/IDS2Eval/results gs://ids2eval-batch-bc67afd1/ids2eval_results`.

**Not in this folder:** the datasets themselves and the tool's cached parquet copies of them, which are inputs, not results. They live in `~/projects/IDS2Eval_data/` (raw files under each dataset name, configs in `configs/`, caches in `output/<dataset>/.cache/`). Several analysis scripts read those caches, so re-running them needs `IDS2Eval_data` in place.

All commands below are run from `~/projects/IDS2Eval` with the project's virtual environment (`venv/bin/python3`).

---

## 1. `analysis/`

Each file is written by one script in `../validation/`; re-running the script overwrites the file. "Paper" gives where the numbers are reported.

### Overview

| File | Script | Paper | Headline result |
|---|---|---|---|
| `validation_results.json` | `run_validation.py` | Section 3.6, Table 1a | 36/36 development fixture evaluations correct |
| `heldout_validation.json` | `heldout_validation.py` | Section 3.6, Table 1a (second family) | 11 checks perfect on held-out fixtures; 9 of 30 clean datasets flagged before the sampling-margin fix |
| `heldout_revalidation.json` | `heldout_revalidation.py` | Section 3.6, Table 1a | After the fix, on fresh seeds: 3 of 30 clean datasets flagged, all by the two single-comparison checks |
| `homogeneity_sensitivity.json` | `homogeneity_sensitivity.py` | Sections 3.4, 6.2, 6.3, Tables 1c and 5 | Per-class `homogeneity_test` intervals and the threshold grid |
| `class_sensitive_seeds.json` | `class_sensitive_seeds.py` | Section 6.3, Table 6b | Random-vs-grouped comparison with class-sensitive metrics (RandomForest) |
| `model_sensitivity.json` | `model_sensitivity.py` | Section 6.3 | The same comparison with LogisticRegression and XGBoost |
| `matched_vs_novel.json` | `matched_vs_novel.py` | Section 6.2 | Accuracy on test rows reused from training vs. novel rows |
| `split_class_composition.json` | `split_class_composition.py` | Section 6.4 | Random and grouped test splits differ by at most 0.04 percentage points in any class share (0.004 excluding CIC-IDS2018) |
| `class_sensitive_results.json` | `class_sensitive_metrics.py` | not cited | Earlier single-seed version of `class_sensitive_seeds.json`, kept for the record |
| `identity_lookup.json` | `identity_rerun.py` | Sections 3.2, 6.3, Table 1c | `identity_column_flag` (training-only lookup) re-scored on five datasets; no flag changes, AUCs move by at most 0.04 |
| `homogeneity_cluster.json` | `homogeneity_cluster.py` | Section 8 | Cluster bootstrap by feature vector: no leakage verdict changes on six datasets |
| `clean_flag_diagnosis.json` | `clean_flag_diagnosis.py` | Section 3.6 | After the unseen-category fix, resplit and robustness flag none of 30 clean datasets (`..._before_encoder_fix.json`: 5 flags before) |
| `cap_sensitivity.json` | `cap_sensitivity.py` (batch) | Section 8 | Accuracy drop unchanged at 200K, 1M and full training rows on CIC-IDS2017-GLF |
| `ddos_unseen_ip.json` | `ddos_unseen_ip.py` | Section 3.6 | About 0.0001 of CICDDoS2019 grouped-split test rows carry an unseen IP |
| `final_holdout.json` | `final_holdout.py` | Section 3.6, Table 1a | Final hold-out, run once after the freeze: no flag on 30 clean corpora; two detection limits |

### `validation_results.json`: development synthetic corpus

What it tests: for 14 checks, one fixture with the check's target defect injected and one matched fixture without it (`validation/fixtures.py`), plus a defect-free control with a 0.5% minority class on which only `class_distribution_report` should react. A check "fires" when its status is `warning` or `flag`.

Structure: a list of 36 records, one per evaluation:

| Field | Meaning |
|---|---|
| `check` | check name |
| `defect` | the condition injected (or the control's description) |
| `polarity` | `positive`, `negative`, or `imbalance` (the control) |
| `expected` / `actual_bucket` | `fires` or `clean` |
| `actual_status` | the check's status: `ok`, `warning` or `flag` |
| `passed` | whether `actual_bucket` equals `expected` |
| `summary` | the check's own one-line summary |

Reproduce: `venv/bin/python3 validation/run_validation.py` (about 3 minutes).

Note: these fixtures shaped one fix (`one_rule_check` now needs to beat the majority-class baseline), which is why the held-out files below exist.

### `heldout_validation.json` and `heldout_revalidation.json`: held-out validation

What they test, in two parts.

- **`part1`:** new fixture generators written after the code was frozen (`validation/heldout_validation.py`). For each of the 14 checks: 5 seeds × 2 class balances (50/50, 90/10) × {weak defect, strong defect, no defect}.
- **`part2`:** the full applicable audit suite (22 checks through the tool's own `run_audit`) on 30 defect-free datasets shaped like flow records (identifier, port, protocol, timestamp and 5-tuple columns; every row its own flow), 10 seeds at each of three class balances (50/50, 10% minority, 2% minority).

`heldout_validation.json` is the first run. Its `part2` found false flags on 9 of 30 clean datasets, all from `resplit_falsification` and `result_robustness_check`. Those two checks were then changed to flag only when the accuracy gap clears its threshold by more than the test sets' sampling margin. `heldout_revalidation.json` re-runs `part1` for the three falsification checks and `part2` for the whole suite on fresh seeds (300-309), giving 3 of 30.

Structure:

| Path | Meaning |
|---|---|
| `part1.<check>.summary.{weak,strong,negative}` | `{n, fired}`: how many fixtures of that kind made the check fire |
| `part1.<check>.runs[]` | one record per fixture: `seed`, `balance`, `strength` (`weak`, `strong` or `negative`), `status` |
| `part2.n_datasets` / `part2.datasets_with_any_flag` | 30 and the number with at least one `flag` |
| `part2.per_check.<check>` | `{flag, warning}` counts across the 30 datasets |
| `part2.runs[]` | per dataset: `balance`, `seed`, and `statuses` (every check's status) |

Key numbers (after the fix): 11 checks detect 10/10 weak and 10/10 strong defects with 0/10 false fires; `resplit_falsification` 7/10 weak, `repeated_seed_falsification_check` 10/10 weak, `result_robustness_check` 5/10 weak, all 10/10 strong and 0/10 false fires. On clean data the 20 checks other than the two single-comparison ones raise no false flag in any of the 60 datasets.

Reproduce: `venv/bin/python3 validation/heldout_validation.py` (about 35 minutes on 2 vCPU) and `venv/bin/python3 validation/heldout_revalidation.py` (about 40 minutes).

### `homogeneity_sensitivity.json`: `homogeneity_test` intervals and threshold grid

What it tests: on six datasets' cached splits (UNSW-NB15, NSL-KDD, CIC-IDS2017 MachineLearningCSV, CICDDoS2019 cleaned subset, ToN-IoT, BoT-IoT), before and after deduplication, plus the full CSE-CIC-IDS2018 split (`cic-ids2018-fullscale/...` keys, merged in from the batch run in `batch_audit_runs/cic-ids2018-split-analysis/`). It computes each class's test-to-train and train-internal match rates and the 95% Newcombe-Wilson interval on their difference. It then re-classifies every class at three margins (0.025, 0.05, 0.10) and three distance cutoffs (1e-6, 1e-3, 1e-1).

Structure: keys are `<dataset>/<stage>` (`stage` is `before` or `after` deduplication), each with:

| Path | Meaning |
|---|---|
| `baseline.<class>` | `test_rate`, `control_rate` (share of sampled rows with a training match at distance < 1e-6), `n_test`, `n_control`, `ci` [low, high] on test minus control, `class` (`leakage`, `cleared` or `inconclusive` at margin 0.05) |
| `grid."cutoff=<c>,margin=<m>"` | counts of classes that are `leakage`, `cleared` and `inconclusive` at that setting |

Key numbers: NSL-KDD has four leakage classes before deduplication (`ipsweep`, `pod`, `smurf`, `portsweep`) and none after. No dataset gains a leakage class at any margin. At the 1e-3 cutoff, NSL-KDD's `smurf` keeps a leakage signature after exact deduplication. The `after` stage gives the `homogeneity_test` entries in the paper's Table 5.

Reproduce: `venv/bin/python3 validation/homogeneity_sensitivity.py` (about 25 minutes; needs the caches in `IDS2Eval_data/output/<dataset>/.cache/`).

### `class_sensitive_seeds.json`: class-sensitive falsification (RandomForest)

What it tests: the same random-versus-grouped comparison as `repeated_seed_falsification_check` (same splits, same 200,000-row training cap, same 100-tree RandomForest, seed paired across both splits). It records balanced accuracy, macro-F1 and per-class recall as well as accuracy. Datasets: ToN-IoT and BoT-IoT (10 seeds), CIC-IDS2017-GLF (5 seeds), run locally, and CSE-CIC-IDS2018 on all 16.2M rows (10 seeds), merged in from the batch run in `batch_audit_runs/cic-ids2018-split-analysis/`.

Structure: per dataset:

| Path | Meaning |
|---|---|
| `seeds[]` | per seed: `seed`, and for `random` and `grouped`: `accuracy`, `balanced_accuracy`, `macro_f1`, `worst_class_recall`, `worst_class_label`, `per_class_recall`, `per_class_support` (test rows per class) |
| `summary.<metric>` | `mean_drop` (random minus grouped, averaged over seeds) with `ci_low` / `ci_high`, a 95% Student-t interval |
| `summary.per_class_recall_drop.<class>` | the same for each class's recall |

Key numbers: accuracy is not materially affected for any dataset. Class-sensitive metrics are stable for ToN-IoT, within +/-0.03 for CIC-IDS2018, and inconclusive for BoT-IoT and CIC-IDS2017, whose rarest classes have only 2-95 test rows. CIC-IDS2018's three web-attack classes (17-123 test rows) are also too small to resolve.

Reproduce: `venv/bin/python3 validation/class_sensitive_seeds.py ton-iot-official:10 bot-iot-official:10 cic-ids2017-glf:5` (several hours; resumes from the file if interrupted).

### `model_sensitivity.json`: other model families

What it tests: the comparison above with LogisticRegression (standardized features) and XGBoost (100 trees, depth 8), on the same splits, seeds and training cap. RandomForest's numbers are in `class_sensitive_seeds.json`. The CSE-CIC-IDS2018 entry comes from the batch run, which scored all three models on the same splits. Structure is the same as that file, except each seed record holds one block per model (`logistic_regression`, `xgboost`) with `accuracy`, `balanced_accuracy` and `macro_f1`, and `summary` is keyed by model.

Reproduce: `venv/bin/python3 validation/model_sensitivity.py ton-iot-official:10 bot-iot-official:10 cic-ids2017-glf:5` (about 4-5 hours on 2 vCPU; resumes if interrupted).

### `matched_vs_novel.json`: does cross-boundary reuse help the classifier?

What it tests: on six cached splits (UNSW-NB15, NSL-KDD, CIC-IDS2017, CICDDoS2019 cleaned subset, ToN-IoT, CIC-IDS2018 500K-row sample), it trains the falsification checks' reference model. It then compares test accuracy on rows whose exact feature vector (the columns `dedup_check` compares) also appears in training with accuracy on novel rows.

Fields per dataset: `test_rows`, `matched_rows`, `matched_share`, `accuracy_matched`, `accuracy_novel`, `accuracy_all`, and `matched_label_agreement` (share of matched rows whose test label equals the majority training label for that vector).

Key numbers: accuracy on matched rows tracks `matched_label_agreement` to within 0.3 points. Reuse lifts UNSW-NB15 (94.3% vs. 86.4%) and NSL-KDD (91.7% vs. 71.7%), and makes no positive difference on near-saturated datasets.

Reproduce: `venv/bin/python3 validation/matched_vs_novel.py` (about 40 minutes; resumes per dataset).

### `split_class_composition.json`: class mix of the paired splits

Fields per dataset: `seeds`, `max_abs_class_share_diff` (largest difference, over classes and seeds, in a class's share of the test set between the random and grouped split) and `max_js_divergence` (largest Jensen-Shannon divergence between the two class distributions). Computed from the per-class supports in `class_sensitive_seeds.json`.

Reproduce: `venv/bin/python3 validation/split_class_composition.py` (seconds).

---

### `identity_lookup.json`: identity check re-scored with the training-only lookup

What it tests: `identity_column_flag` as redesigned (counts of each identifier value by class from the training partition only, smoothed toward the class prior, unseen values scored with the prior) on CIC-IDS2017, CIC-IDS2017-GLF, ToN-IoT, BoT-IoT and the full CSE-CIC-IDS2018 split (rebuilt from the batch run's cached data with the audit's seed-0 split), before and after dedup. Dedup is done on 64-bit row hashes with `dataset.dedup`'s order of operations and reproduces Table 6's counts exactly.

Fields per dataset: `train_rows`, `test_rows`, `dedup` (the counts), and for `before` and `after`: `status`, `standalone_auc` (all test rows, the flagged value), `seen_only_auc`, `seen_coverage` (share of test rows whose value occurs in training), `suggested_drop`, `by_class`.

Reproduce: `venv/bin/python3 validation/identity_rerun.py cic-ids2017 ton-iot-official ...`; for CIC-IDS2018, `cic-ids2018-fullscale:/path/to/combined.parquet` (the batch cache, 1.5 GB).

### `homogeneity_cluster.json`: cluster-aware intervals for `homogeneity_test`

What it tests: the same samples `homogeneity_test` draws, with a 95% percentile bootstrap that resamples whole encoded feature vectors (all rows sharing a vector together) instead of rows, next to the row-level Newcombe interval. Keys `<dataset>/<before|after>`; per class: rates, sample sizes, `test_vectors` / `control_vectors` (distinct vectors in each sample), `row_ci`, `row_class`, `cluster_ci`, `cluster_class`.

Reading it: after dedup every sampled row is its own vector, so the two intervals agree in substance; where both rates are exactly 0 the bootstrap interval collapses to [0, 0] and the row-level interval is the right one. Before dedup repeated vectors widen some intervals (CIC-IDS2017 `DoS Hulk`, `DoS Slowhttptest` move from cleared to inconclusive). No leakage verdict changes.

Reproduce: `venv/bin/python3 validation/homogeneity_cluster.py` (about 30 minutes).

### `clean_flag_diagnosis.json`: why one-shot checks flagged clean data

What it tests: the clean flow-like datasets of the second family (seeds 300-309, three balances), recording behind each verdict of `resplit_falsification` and `result_robustness_check` the accuracies, gap, sampling margin, test sizes and per-condition accuracies, with `repeated_seed_falsification_check`'s interval alongside. `clean_flag_diagnosis_before_encoder_fix.json` is the same run before the unseen-category fix: there the 10%-minority datasets reach accuracies such as 0.45 against a 0.90 majority, the signature of the bug.

Reproduce: `venv/bin/python3 validation/clean_flag_diagnosis.py 300` (about 45 minutes).

### `cap_sensitivity.json`: the 200,000-row training cap

What it tests: on CIC-IDS2017-GLF, 5 seeds, the reference random forest fitted on 200K, 1M and all 2,264,594 training rows for both the random and the grouped split, scored on the full test set. Per seed and split, per cap: `accuracy`, `balanced_accuracy`, `macro_f1`, `fit_rows`, `seconds`; `summary.<cap>.<metric>` holds the paired mean drop and Student-t interval.

Key numbers: accuracy drop -0.00001, 0.00000, +0.00001 (200K, 1M, full); macro-F1 drop about 0, +0.049, +0.046, every interval including zero.

Reproduce: run on a batch VM (`batch_audit_runs/cap-sensitivity-glf/`), or locally: `venv/bin/python3 validation/cap_sensitivity.py cic-ids2017-glf 5` (many hours on 2 vCPU).

### `ddos_unseen_ip.json`: unseen IPs in CICDDoS2019's grouped split

What it computes: streaming both official day files, the number of distinct 5-tuple groups per Source IP and Destination IP, and from it the expected share of grouped-split test rows whose IP value never occurs in training (each group lands in test with probability about 0.2). Result: about 0.00005 per column, 0.0001 as an upper bound for either, so the unseen-category fix cannot move the published CICDDoS2019 resplit result.

Reproduce: `venv/bin/python3 validation/ddos_unseen_ip.py <train-full.csv.gz> <test-full.csv.gz>` (about an hour locally).

### `final_holdout.json`: the final synthetic hold-out

What it is: a third generator family, committed before it ran, run once after the `paper-method-freeze` tag (the first run was stopped by a session ending after 13 results and restarted unchanged; it reproduced those 13 exactly, see `logs/`). Four classes under two prior regimes, flow-like features with a moderate class signal, new defect mechanisms. Same structure as `heldout_validation.json`, with `regime` in place of `balance`; `part2.runs[].non_ok_summaries` holds the summary of every non-ok check.

Key numbers: no flag on any of 30 clean corpora (24 carry a warning); `one_rule_check` 0/10 weak and strong (a stump cannot express a three-threshold rule); `temporal_leakage_check` misses the weak defect.

Reproduce: `venv/bin/python3 validation/final_holdout.py` refuses to run when the output file exists, by design.

---

## 2. `logs/`

| File | From |
|---|---|
| `class_sensitive_seeds.log` | `class_sensitive_seeds.py` (old 4-vCPU VM, resumed once after a VM shutdown) |
| `homogeneity_sensitivity.log` | `homogeneity_sensitivity.py` |
| `matched_vs_novel.log` | `matched_vs_novel.py` |
| `heldout_validation.log`, `heldout_revalidation.log` | the two held-out runs; each clean dataset's flags and warnings are listed line by line |
| `model_sensitivity.log` | `model_sensitivity.py`, one line per seed |
| `clean_flag_diagnosis.log`, `clean_flag_diagnosis_before_encoder_fix.log` | `clean_flag_diagnosis.py` after and before the unseen-category fix |
| `ddos_unseen_ip.log` | `ddos_unseen_ip.py` |
| `final_holdout.log`, `final_holdout_interrupted_0708.log` | the final hold-out run, and the first attempt that a session ending stopped |
| `frozen_rerun_queue.sh`, `frozen_rerun_queue.log` | the queue that re-ran the local audits at the frozen code on 2026-10-07 |
| `run_queue.sh`, `run_queue.log` | the shell script that ran the long jobs one after another on the local VM, and its start/finish times |

---

## 3. `local_audit_runs/`

Full audit runs made with `ids2eval run --config <config>` on the local VM: a 4-vCPU, 15 GB machine until 2026-10-04, then 2 vCPU, 7.8 GB with 16 GB swap. They were moved here from `~/projects/IDS2Eval_data/output/`. The layout is `<dataset config>/runs/<run start time>/`, which the dashboard reads directly: `venv/bin/python3 -m ids2eval.dashboard --output results/local_audit_runs/<dataset>`.

### Files in a run folder

| File | Contents |
|---|---|
| `scorecard.json` | the machine-readable scorecard: verdict, counts, every check's status and summary before and after deduplication, deduplication effect, dataset fingerprint, tool version and git commit |
| `SCORECARD.md`, `SCORECARD.html` | the same scorecard rendered for reading |
| `scorecard.png`, `scorecard.pdf` | the optional one-page chart (only where enabled in the config) |
| `audit_report_before.json`, `audit_report_after.json` | every check's full output, including `details`, on the raw split and after deduplication |
| `dataset_fingerprint.json` | row and feature counts, class distribution, schema, content and source hashes |
| `resolved_config.json` | the complete configuration the run used |
| `environment.json` | Python version, platform, IDS2Eval version, package versions |
| `run_status.json` | `completed`, or the stage and error where a run failed |

Folders without `scorecard.json` are runs that were stopped or crashed before finishing (for example `cic-ids2017-glf`'s only local attempt, which ran out of memory and was moved to the batch cluster).

### Which runs the paper uses

The paper's Tables 5 and 6 and the dataset paragraphs of Section 6 use runs made with the frozen code (tag `paper-method-freeze`, plus commit `f452cab`, which only speeds up `feature_auc_ranking_check` without changing its output):

| Dataset | Run folder | Rows | Notes |
|---|---|---|---|
| UNSW-NB15 | `local_audit_runs/unsw-nb15/runs/2026-10-07_104948_807678` | 257,673 | official train/test pair |
| NSL-KDD | `local_audit_runs/nsl-kdd/runs/2026-10-07_105131_090470` | 148,517 | official KDDTrain+/KDDTest+ |
| CIC-IDS2017 | `local_audit_runs/cic-ids2017/runs/2026-10-07_111725_018420` | 2,830,743 | MachineLearningCSV release |
| CSE-CIC-IDS2018 | `batch_audit_runs/cic-ids2018-fullscale/runs/2026-09-28_225428_095778` | 16,232,943 | earlier code; it has no string features, so the encoding fix cannot change it, and its identity AUCs and `homogeneity_test` were recomputed separately (`analysis/identity_lookup.json`, `batch_audit_runs/cic-ids2018-split-analysis/`) |
| CICDDoS2019 | `batch_audit_runs/cic-ddos2019-fullscale-main/out/runs/2026-10-07_101104_616996` | 70,427,637 | official release, official day split |
| ToN-IoT | `local_audit_runs/ton-iot-official/runs/2026-10-07_105328_897471` | 211,043 | official `Train_Test_Network.csv` |
| BoT-IoT | `batch_audit_runs/bot-iot-official-rerun/out/runs/2026-10-07_131115_277703` | 3,668,522 | official 5%-reduced release |
| CIC-IDS2017-GLF (Section 6.3) | `batch_audit_runs/cic-ids2017-glf-rerun/out/runs/2026-10-07_131149_314813` | 2,830,743 | GeneratedLabelledFlows release, 10-seed falsification |

At the frozen code these runs reproduce every Table 5 count directly, including `homogeneity_test`, which earlier runs had needed correcting by hand. Compared with the earlier runs, the only status changes are in `homogeneity_test` (the method changed); the identity redesign and the encoding fix changed no status on any dataset.

The other folders are history: the earlier runs of each dataset (from before the freeze), `cic-ddos2019` (the cleaned Kaggle subset an earlier pass audited), `bot-iot` and `ton-iot` (500K-row samples of the NetFlow-V2 conversions), `cic-ids2018` (500K-row sample of the official release, the source of the 13.15% duplication figure), and `cic-iot2023` (500K-row sample of a dataset later excluded).

The local report files of the earlier runs were re-rendered on 2026-10-04 to show the verdict "Review Required" instead of "Failed" (scorecard schema 1.3). `archives/scorecards_backup_pre_review_required.tar.gz` keeps them as they were.

### `archives/` (not in git)

| File | Contents |
|---|---|
| `hand_built_unsw_cic_results.zip` | Results of the original hand-built UNSW-NB15 and CIC-IDS2018 analysis that predates IDS2Eval: metrics, logs and plots behind Sections 4-5, Table 4 and Figure 1 (`results/cic/plots/cic_binary_model_shap_bar.png`) |
| `scorecards_backup_pre_review_required.tar.gz` | the `output/` report files as they were before the 2026-10-04 re-render |

### Note for new runs

New runs still write to `~/projects/IDS2Eval_data/output/` (each config's `output.dir`). The tool's previous-run comparison only looks there, so a new run will not be compared against the runs in this folder unless they are copied back.

---

## 4. `batch_audit_runs/`

Runs made on Google Cloud Batch (spot instances, us-east1), copied verbatim from `gs://ids2eval-batch-bc67afd1/results/`, where the originals remain. Each folder has the job's `config.yaml`, its console `run.log`, `host.txt` (the VM it ran on), and `runs/<run>/` with the same files as a local run. Folders from 2026-10-07 on use `validation/batch_run.sh`, which keeps the run under `out/` and the logs (`run.log`, one `attempt_<n>.log` per attempt, `memlog.txt`) under `logs/`; `out/.checkpoint/` holds the per-check checkpoint a resumed attempt reads. These copies were not re-rendered, so their reports still show the earlier `failed` verdict wording (schema 1.2).

| Folder | What it is | Machine | Runtime | Paper |
|---|---|---|---|---|
| `cic-ids2018-fullscale/` | full audit with 10-seed falsification on all 16,232,943 rows of the official AWS release | n2-highmem-16 (16 vCPU, 128 GB) | 9.5 h for the successful attempt (19.7 h job including earlier attempts) | Tables 5, 6, 6a |
| `cic-ddos2019-fullscale-resplit/` | falsification checks only (resplit, robustness, 5 seeds) on the full official release, 70,427,637 rows | n2-custom-16 (16 vCPU, 384 GB) | 18.6 h, after earlier attempts ran out of memory on smaller machines | Table 6a, Section 6.3 |
| `cic-ids2017-glf/` | full audit with 10-seed falsification on the GeneratedLabelledFlows release (real 5-tuple) | n2-standard-4 (4 vCPU, 16 GB) | 3.7 h | Table 6a, Section 6.3 |
| `bot-iot-official/` | full audit with 10-seed falsification on the 5%-reduced release | n2-standard-4 (4 vCPU, 16 GB) | 2.4 h | superseded by the local re-run above |
| `iot23/` | IoT-23 attempt: a checkpoint and a memory trace only | n2-custom-16 (384 GB) | did not complete (out of memory) | Section 6.1 (exclusion) |
| `cic-ddos2019-fullscale-main/` | full default audit (19 checks) on the official release with its own day split, 50,063,112 train and 20,364,525 test rows, frozen code | n2-custom-30 (30 vCPU, 384 GB) | 3.7 h, resuming five checkpointed checks from an attempt cancelled to speed up `feature_auc_ranking_check` (its incomplete run folder `2026-10-07_075950_353883` is kept) | Tables 5, 6, 9; Section 6.1 |
| `bot-iot-official-rerun/` | BoT-IoT full audit with 10-seed falsification at the frozen code | n2-highmem-8 (8 vCPU, 64 GB) | 1.0 h | Tables 5, 6a |
| `cic-ids2017-glf-rerun/` | CIC-IDS2017-GLF full audit with 10-seed falsification at the frozen code | n2-standard-16 (16 vCPU, 64 GB) | 1.3 h | Table 6a, Section 6.3 |
| `cap-sensitivity-glf/` | `validation/cap_sensitivity.py`: reference model at 200K, 1M and full training rows, 5 seeds | n2-standard-16 | 0.8 h | Section 8 |
| `cic-ids2018-split-analysis/` | `validation/batch_split_analysis.py` on all 16,232,943 rows: `homogeneity_test` before and after dedup, and 10 paired seeds scoring RandomForest, LogisticRegression and XGBoost | n2-highmem-16 (16 vCPU, 128 GB), no external IP | 3.6 h including one spot preemption; peak memory 27 GB | Tables 5, 6b, 9; Sections 6.3, 8 |

`memlog.txt` (in `cic-ddos2019-fullscale-resplit/` and `iot23/`) is a 10-second trace of the job's memory use, recorded to find the out-of-memory point.

`cic-ids2018-split-analysis/` has a different layout from the audit runs, because it is a staged analysis, not an `ids2eval` run:

| Path | Contents |
|---|---|
| `out/state.json` | each stage (`load`, `homogeneity`, `seeds`, `summarize`) with its status, attempts, start and finish times |
| `out/homogeneity.json` | the audited split's sizes, dedup statistics, and for `before` and `after` dedup: the check's own output, per-class baseline, and threshold grid |
| `out/seeds/seed_<n>.json` | one paired seed: for the `random` and `grouped` split, the RandomForest metrics (`random_forest`) and the LogisticRegression and XGBoost metrics (`other_models`), plus each unit's runtime |
| `out/class_sensitive_seeds.json`, `out/model_sensitivity.json` | the seeds summarized in the same layout as the files in `analysis/`, into which they were merged |
| `logs/analysis.log` | the Python log across both attempts, with one summary line per seed |
| `logs/attempt_<n>.log` | the VM script's log per attempt (attempt 0 ended in a spot preemption) |
| `logs/memlog.txt` | `free -m` every 10 seconds |
| `host.txt` | VM shape of the last attempt |

The cached dataset (`out/cache/combined.parquet`) was left in the bucket only (`gs://ids2eval-batch-bc67afd1/results/cic-ids2018-split-analysis/`). To rerun, see the header of `validation/batch_split_analysis.sh`: the job needs `WHEELS_URI` and a VM without external IP, because the project's org policy denies external IPs.
