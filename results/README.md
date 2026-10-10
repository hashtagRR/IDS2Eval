# IDS2Eval results

Every result behind the paper *IDS²Eval: A Falsification-Oriented Framework for Auditing
Machine-Learning Intrusion Detection Benchmarks* (in preparation). Paper locations below refer
to its current draft: Sections 1-9, Tables 1-15, and supplementary Tables S1-S7.

| Folder or file | What it is | In git |
|---|---|---|
| [`analysis/`](#analysis) | JSON outputs of the scripts in [`../validation/`](../validation/) | yes |
| [`logs/`](#logs) | console logs of those scripts, and the queue scripts that ran them | yes |
| [`local_audit_runs/`](#local_audit_runs) | full IDS2Eval audit runs on a local VM, one folder per dataset | yes, except `archives/` |
| [`batch_audit_runs/`](#batch_audit_runs) | full-scale audit runs on Google Cloud Batch | yes |
| `configs/` | the dataset configuration behind every run the paper uses, with data paths reduced to `data/<file>` | yes |
| `dataset_manifest.md`, `.json` | source, file name, size and SHA-256 of the uncompressed content of every dataset file the audits read | yes |

## Reproducing

The datasets are third-party and not included. Download them from the sources in
`dataset_manifest.md`, check each file's SHA-256 there, and put them in one data folder. Then:

- **An audit:** copy the matching file from `configs/`, point its `data/<file>` paths at your
  data folder, and run `venv/bin/ids2eval run --config <config>.yaml`.
- **An analysis script:** set `IDS2EVAL_DATA` to the data folder and run the command given for
  each file below, from the repository root. Scripts marked *cached* read the parquet caches an
  audit writes to `<output.dir>/<dataset>/.cache/`, so run the dataset's audit first.

Long jobs resume from their output file when interrupted. Several were run on Cloud Batch;
`validation/batch_*.sh` are those runners, and each one's header lists its inputs.

## analysis

Each file is written by one script in `../validation/`; re-running the script overwrites it.

| File | Script | Paper | Headline result |
|---|---|---|---|
| `validation_results.json` | `run_validation.py` | Section 3.6, Table S1 | 36/36 development fixture evaluations correct |
| `heldout_validation.json` | `heldout_validation.py` | Section 3.6, Supplement D.2 | 11 checks perfect on held-out fixtures; 9 of 30 clean datasets flagged before the sampling-margin fix |
| `heldout_revalidation.json` | `heldout_revalidation.py` | Section 3.6, Supplement D.2 | after the fix, on fresh seeds: 3 of 30 clean datasets flagged, all by the two single-comparison checks |
| `clean_flag_diagnosis.json` | `clean_flag_diagnosis.py` | Supplement D.2 | after the unseen-category fix, resplit and robustness flag none of 30 clean datasets |
| `final_holdout.json` | `final_holdout.py` | Section 3.6, Table S1 | run once after the freeze: no flag on 30 clean corpora; two detection limits |
| `homogeneity_sensitivity.json` | `homogeneity_sensitivity.py` | Sections 3.4, 6.2; Table S3 | per-class `homogeneity_test` intervals and the threshold grid |
| `homogeneity_cluster.json` | `homogeneity_cluster.py` | Sections 3.9, 8 | cluster bootstrap by feature vector: no leakage verdict changes on six datasets |
| `homogeneity_coverage.json` | `homogeneity_coverage.py` | Section 3.9, Table 6 | interval coverage at least 99.5% for the audited split, no wrong verdict in 6,000 intervals |
| `workflow_ablation.json` | `workflow_ablation.py` | Section 3.8 (earlier design) | first design of the workflow ablation, revised after review |
| `workflow_ablation_v2.json` | `workflow_ablation_v2.py` | Section 3.8, Tables 3-5 | each stage detects its own condition; the interventions alone decide inflation (29/30) |
| `identity_lookup.json` | `identity_rerun.py` | Section 3.7, Supplement D.3 | `identity_column_flag` re-scored with the training-only lookup: no flag changes, AUCs move by at most 0.04 |
| `port_protocol_lookup.json` | `port_protocol_lookup.py`, `port_protocol_lookup_stream.py` | Section 3.7, Table S7 | `port_protocol_shortcut_check` re-scored with the lookup: every flag stands |
| `matched_vs_novel.json` | `matched_vs_novel.py` | Section 6.2 | raw accuracy on reused vs. novel test rows |
| `reuse_stratified.json` | `reuse_stratified.py` | Section 6.2 | the reuse advantage is a class-mix effect: within classes -0.56 (UNSW-NB15) and -1.01 (NSL-KDD) points |
| `class_sensitive_seeds.json` | `class_sensitive_seeds.py` | Section 6.3, Table S4 | random vs. grouped split with class-sensitive metrics (random forest) |
| `model_sensitivity.json` | `model_sensitivity.py` | Section 6.3, Supplement C.4 | the same comparison with logistic regression and XGBoost |
| `host_holdout.json` | `host_holdout.py` | Section 6.3 | source- and destination-host-disjoint 5-fold cross-validation on ToN-IoT and BoT-IoT |
| `host_holdout_diag.json` | `host_holdout_diag.py` | Section 6.3, Table 12 | per-fold class and host support, endpoint connectivity, host-clustered intervals, unseen-identifier confusion |
| `split_class_composition.json` | `split_class_composition.py` | Section 6.4 | random and grouped test splits differ by at most 0.04 percentage points in any class share |
| `flood_comparison.json` | `flood_comparison.py` | Section 6.5, Table 14 | Flood et al.'s released heuristics and IDS2Eval on the same ToN-IoT and UNSW-NB15 artifacts |
| `cap_sensitivity.json` | `cap_sensitivity.py` | Section 8 | accuracy drop unchanged at 200K, 1M and all training rows on CIC-IDS2017-GLF |
| `ddos_unseen_ip.json` | `ddos_unseen_ip.py` | Supplement D.2 | about 0.0001 of CICDDoS2019 grouped-split test rows carry an unseen IP |
| `class_sensitive_results.json` | `class_sensitive_metrics.py` | not cited | earlier single-seed version of `class_sensitive_seeds.json`, kept for the record |

### Synthetic validation

**`validation_results.json`.** For 14 checks, one fixture with the check's target defect injected
and one matched fixture without it (`validation/fixtures.py`), plus a defect-free control with a
0.5% minority class on which only `class_distribution_report` should react. A check fires when
its status is `warning` or `flag`. A list of 36 records with `check`, `defect`, `polarity`
(`positive`, `negative` or `imbalance`), `expected` and `actual_bucket` (`fires` or `clean`),
`actual_status`, `passed` and the check's `summary`. These fixtures shaped one fix
(`one_rule_check` must beat the majority-class baseline), which is why the held-out files exist.
Reproduce: `venv/bin/python3 validation/run_validation.py` (about 3 minutes).

**`heldout_validation.json`, `heldout_revalidation.json`.** `part1`: generators written after the
code was frozen; for each of the 14 checks, 5 seeds × 2 class balances × {weak, strong, no
defect}. `part2`: the full applicable suite (22 checks through `run_audit`) on 30 defect-free
flow-like datasets. The first run found false flags on 9 of 30 clean datasets, all from
`resplit_falsification` and `result_robustness_check`; those checks now flag only when the gap
clears its threshold by more than the sampling margin, and the re-run on fresh seeds (300-309)
gives 3 of 30. Paths: `part1.<check>.summary.{weak,strong,negative}` (`{n, fired}`),
`part1.<check>.runs[]`, `part2.per_check.<check>`, `part2.runs[]`. Reproduce:
`validation/heldout_validation.py` (about 35 minutes on 2 vCPU) and
`validation/heldout_revalidation.py` (about 40 minutes).

**`clean_flag_diagnosis.json`.** The accuracies, gap, sampling margin and test sizes behind each
verdict of the two single-comparison checks on the clean datasets above, with
`repeated_seed_falsification_check`'s interval alongside. The `_before_encoder_fix` file is the
same run before the unseen-category fix. Reproduce: `validation/clean_flag_diagnosis.py 300`
(about 45 minutes).

**`final_holdout.json`.** A third generator family, committed before it ran and run once after
the `paper-method-freeze` tag (a first attempt stopped after 13 results and was restarted
unchanged; it reproduced those 13 exactly, see `logs/`). Same structure as
`heldout_validation.json`, with `regime` in place of `balance`. `validation/final_holdout.py`
refuses to run when the output file exists, by design.

### The nearest-neighbor test

**`homogeneity_sensitivity.json`** (*cached*). Each class's test-to-train and train-internal match
rates with the 95% Newcombe interval on their difference, before and after deduplication, on six
cached splits plus the full CSE-CIC-IDS2018 split (merged from
`batch_audit_runs/cic-ids2018-split-analysis/`), re-classified at margins 0.025, 0.05 and 0.10 and
distance cutoffs 1e-6, 1e-3 and 1e-1. Keys `<dataset>/<before|after>` with `baseline.<class>` and
`grid."cutoff=<c>,margin=<m>"`. Reproduce: `validation/homogeneity_sensitivity.py` (about 25
minutes).

**`homogeneity_cluster.json`** (*cached*). The same samples with a percentile bootstrap that
resamples whole encoded feature vectors, next to the Newcombe interval. Before deduplication it
moves CIC-IDS2017 `DoS Hulk` and `DoS Slowhttptest` from cleared to inconclusive; no leakage
verdict changes. Reproduce: `validation/homogeneity_cluster.py` (about 30 minutes).

**`homogeneity_coverage.json`.** Simulated populations with a known answer (500 datasets each),
scored with the check's interval and the vector bootstrap. `summary.<population>` holds coverage,
widths and verdict rates; `rows[]` holds every interval with its own split's full difference
(`full_diff`), which is the estimand Section 3.9 judges against. Reproduce:
`validation/homogeneity_coverage.py --jobs 8` (a few minutes on 8 vCPU).

### The workflow ablation

**`workflow_ablation_v2.json`** (current) and **`workflow_ablation.json`** (first design). Nine
synthetic scenarios, 10 generator seeds each, scored with the frozen checks. `runs[]` holds per
corpus the deployment gap, the reuse share, each stage's output, both interventions' intervals and
the decision rules' verdicts; `summary.scenarios.<name>` holds the evidence-quality and held-out
decision-quality tallies and `summary.d1_cutoff` the fitted reuse-share cutoff. The first design
read a `dedup_check` flag as a claim of material inflation and scored truth per corpus from one
noisy deployment sample; it is kept for the record. Reproduce:
`validation/workflow_ablation_v2.py --jobs 8` (about 8 minutes on 8 vCPU).

### Identifier and port checks

**`identity_lookup.json`.** `identity_column_flag` as redesigned (training-only value counts,
smoothed toward the class prior, unseen values scored with the prior) on CIC-IDS2017,
CIC-IDS2017-GLF, ToN-IoT, BoT-IoT and the full CSE-CIC-IDS2018 split, before and after
deduplication, with `standalone_auc`, `seen_only_auc` and `seen_coverage`. Deduplication
reproduces Table 10's counts exactly. Reproduce: `validation/identity_rerun.py <dataset> ...`.

**`port_protocol_lookup.json`.** `port_protocol_shortcut_check`'s frozen AUC next to the lookup
AUC on the (port, protocol) pair, before and after deduplication, on ToN-IoT, CSE-CIC-IDS2018 and
CICDDoS2019. Reproduce: `validation/port_protocol_lookup.py` (ToN-IoT, *cached*) and
`validation/port_protocol_lookup_stream.py <dataset>` (streams the full CIC releases).

### Reuse and splits

**`matched_vs_novel.json`** (*cached*). Accuracy of the falsification checks' reference model on
test rows whose exact feature vector also appears in training, against novel rows, on six cached
splits, with `matched_label_agreement` (share of matched rows whose label equals the majority
training label for that vector). Reproduce: `validation/matched_vs_novel.py` (about 40 minutes).

**`reuse_stratified.json`.** The same comparison on the official UNSW-NB15 and NSL-KDD
partitions, within each class (UNSW-NB15 `attack_cat`, NSL-KDD label) with novel-row accuracy
reweighted to the reused rows' class mix, over five model seeds and with bootstrap intervals.
`mean_over_seeds` holds the raw and class-adjusted advantage and their contribution to overall
accuracy; `runs[].adjusted.per_stratum` the per-class accuracies. Reproduce:
`validation/reuse_stratified.py` (about a minute on 4 vCPU).

**`class_sensitive_seeds.json`.** The random-versus-grouped comparison of
`repeated_seed_falsification_check` (same splits, training cap and forest, seed paired across
both splits) with balanced accuracy, macro-F1 and per-class recall. ToN-IoT and BoT-IoT (10
seeds), CIC-IDS2017-GLF (5) and CSE-CIC-IDS2018 (10, merged from the batch run).
`summary.<metric>` holds the mean drop with a 95% Student-*t* interval. Reproduce:
`validation/class_sensitive_seeds.py ton-iot-official:10 bot-iot-official:10 cic-ids2017-glf:5`
(several hours).

**`model_sensitivity.json`.** The same with logistic regression and XGBoost (100 trees, depth 8).
Reproduce: `validation/model_sensitivity.py ton-iot-official:10 bot-iot-official:10
cic-ids2017-glf:5` (about 5 hours on 2 vCPU).

**`split_class_composition.json`.** Largest difference in any class's test share, and largest
Jensen-Shannon divergence, between the paired random and grouped splits. Reproduce:
`validation/split_class_composition.py` (seconds).

**`host_holdout.json`, `host_holdout_diag.json`.** Source- and destination-host-disjoint 5-fold
cross-validation with out-of-fold predictions on the same rows as random folds, identifiers kept
and dropped. The diagnostics add, per fold and class, training and test rows and hosts, held-out
hosts seen in the other role, unseen-identifier shares, confusion counts, the connected components
of the host graph, and host-clustered bootstrap intervals. Reproduce:
`validation/host_holdout.py ton-iot-official:3 bot-iot-official:2` and
`validation/host_holdout_diag.py ton-iot-official bot-iot-official` (BoT-IoT ran out of memory on a
7.8 GB VM; it ran on Batch with 64 GB, `validation/batch_review4.sh`).

**`cap_sensitivity.json`.** The reference forest fitted on 200K, 1M and all 2,264,594 training
rows of CIC-IDS2017-GLF, 5 seeds, both splits. Accuracy drop -0.00001, 0.00000, +0.00001; macro-F1
drop about 0, +0.049, +0.046, every interval including zero. Ran on Batch
(`batch_audit_runs/cap-sensitivity-glf/`).

**`ddos_unseen_ip.json`.** From both official CICDDoS2019 day files, the expected share of
grouped-split test rows whose IP value never occurs in training: about 0.0001 at most, so the
unseen-category fix cannot move the published resplit result. Reproduce:
`validation/ddos_unseen_ip.py <train-full.csv.gz> <test-full.csv.gz>`.

### Comparison with Flood et al.'s tool

**`flood_comparison.json`.** Flood et al.'s released heuristics (github.com/DataBadSmells/DataBadSmells,
commit 88f3278) run per attack class with their pinned packages, and the overlapping IDS2Eval
checks, on ToN-IoT and UNSW-NB15, with wall times on the same machine. `<dataset>.flood` holds
their per-class outputs and the metadata actually used (drop fields absent from the artifact are
recorded); `<dataset>.per_class` the side-by-side summary; `_class_vs_benign_auc` IDS2Eval's AUC
statistic on their class-versus-benign task. Reproduce: `validation/flood_comparison.py
<path-to-their-tool> ton-iot-official unsw-nb15` with `FLOOD_PY` pointing at a Python 3.11
environment with numpy 1.25.2, pandas 2.1.4 and scikit-learn 1.3.2
(`validation/batch_review4.sh` builds one).

## logs

| File | From |
|---|---|
| `class_sensitive_seeds.log`, `homogeneity_sensitivity.log`, `matched_vs_novel.log`, `model_sensitivity.log`, `ddos_unseen_ip.log` | the script of the same name |
| `heldout_validation.log`, `heldout_revalidation.log` | the two held-out runs; each clean dataset's flags and warnings line by line |
| `clean_flag_diagnosis.log`, `clean_flag_diagnosis_before_encoder_fix.log` | `clean_flag_diagnosis.py` after and before the unseen-category fix |
| `final_holdout.log`, `final_holdout_interrupted_0708.log` | the final hold-out run, and the first attempt that was stopped |
| `frozen_rerun_queue.sh`, `frozen_rerun_queue.log` | the queue that re-ran the local audits at the frozen code on 2026-10-07 |
| `run_queue.sh`, `run_queue.log` | the queue that ran the long local jobs one after another |

## local_audit_runs

Full audit runs made with `ids2eval run --config <config>` on a local VM (4 vCPU, 15 GB until
2026-10-04, then 2 vCPU, 7.8 GB with 16 GB swap). The layout is
`<dataset config>/runs/<run start time>/`, which the dashboard reads directly:
`venv/bin/python3 -m ids2eval.dashboard --output results/local_audit_runs/<dataset>`.

| File in a run folder | Contents |
|---|---|
| `scorecard.json` | verdict, counts, every check's status and summary before and after deduplication, deduplication effect, dataset fingerprint, tool version and git commit |
| `SCORECARD.md`, `SCORECARD.html` | the same scorecard rendered for reading |
| `scorecard.png`, `scorecard.pdf` | the optional one-page chart, where enabled |
| `audit_report_before.json`, `audit_report_after.json` | every check's full output, including `details` |
| `dataset_fingerprint.json` | row and feature counts, class distribution, schema, content and source hashes |
| `resolved_config.json`, `environment.json`, `run_status.json` | the complete configuration, the software environment, and `completed` or the stage where a run failed |

Folders without `scorecard.json` are runs stopped before finishing.

**Which runs the paper uses.** Tables 9 and 10 and the dataset paragraphs of Section 6 use runs
made with the frozen code (tag `paper-method-freeze`, plus commit `f452cab`, which only speeds up
`feature_auc_ranking_check`):

| Dataset | Run folder | Rows | Notes |
|---|---|---|---|
| UNSW-NB15 | `local_audit_runs/unsw-nb15/runs/2026-10-07_104948_807678` | 257,673 | official train/test pair |
| NSL-KDD | `local_audit_runs/nsl-kdd/runs/2026-10-07_105131_090470` | 148,517 | official KDDTrain+/KDDTest+ |
| CIC-IDS2017 | `local_audit_runs/cic-ids2017/runs/2026-10-07_111725_018420` | 2,830,743 | MachineLearningCSV release |
| CSE-CIC-IDS2018 | `batch_audit_runs/cic-ids2018-fullscale/runs/2026-09-28_225428_095778` | 16,232,943 | earlier code; it has no string features, so the encoding fix cannot change it, and its identity AUCs and `homogeneity_test` were recomputed separately |
| CICDDoS2019 | `batch_audit_runs/cic-ddos2019-fullscale-main/out/runs/2026-10-07_101104_616996` | 70,427,637 | official release, official day split |
| ToN-IoT | `local_audit_runs/ton-iot-official/runs/2026-10-07_105328_897471` | 211,043 | official `Train_Test_Network.csv` |
| BoT-IoT | `batch_audit_runs/bot-iot-official-rerun/out/runs/2026-10-07_131115_277703` | 3,668,522 | official 5%-reduced release |
| CIC-IDS2017-GLF | `batch_audit_runs/cic-ids2017-glf-rerun/out/runs/2026-10-07_131149_314813` | 2,830,743 | GeneratedLabelledFlows release, 10-seed falsification (Section 6.3) |

The other folders are history: earlier runs of each dataset from before the freeze,
`cic-ddos2019` (a cleaned Kaggle subset), `bot-iot` and `ton-iot` (500K-row samples of the
NetFlow-V2 conversions), `cic-ids2018` (a 500K-row sample of the official release, the source of
the 13.15% duplication figure) and `cic-iot2023` (a 500K-row sample of a dataset later excluded).
Earlier runs' report files were re-rendered on 2026-10-04 to show the verdict "Review Required"
instead of "Failed"; `archives/` keeps the originals.

**`archives/` (not in git).** `hand_built_unsw_cic_results.zip` holds the results of the original
hand-built UNSW-NB15 and CIC-IDS2018 analysis that predates IDS2Eval (behind Section 4 and the
CIC-IDS2018 investigation the introduction mentions); `scorecards_backup_pre_review_required.tar.gz`
holds the report files as they were before the re-render.

## batch_audit_runs

Runs on Google Cloud Batch spot instances, copied verbatim from the project's storage bucket. Each
folder has the job's `config.yaml`, its `run.log`, `host.txt` (the VM), and `runs/<run>/` with
the same files as a local run. Folders from 2026-10-07 on use `validation/batch_run.sh`, which
keeps the run under `out/` and the logs under `logs/` (`run.log`, one `attempt_<n>.log` per
attempt, `memlog.txt`); `out/.checkpoint/` holds the per-check checkpoint a resumed attempt reads.

| Folder | What it is | Machine | Runtime | Paper |
|---|---|---|---|---|
| `cic-ids2018-fullscale/` | full audit with 10-seed falsification on all 16,232,943 rows of the official AWS release | n2-highmem-16 (16 vCPU, 128 GB) | 9.5 h for the successful attempt | Tables 9-11 |
| `cic-ddos2019-fullscale-resplit/` | falsification checks only (5 seeds) on all 70,427,637 rows | n2-custom-16 (16 vCPU, 384 GB) | 18.6 h | Table 11, Section 6.3 |
| `cic-ddos2019-fullscale-main/` | full default audit on the official release with its own day split, frozen code | n2-custom-30 (30 vCPU, 384 GB) | 3.7 h | Tables 9, 10; Table S6 |
| `cic-ids2017-glf/`, `cic-ids2017-glf-rerun/` | full audit with 10-seed falsification on the GeneratedLabelledFlows release (real 5-tuple); the rerun is at the frozen code | n2-standard-4 / n2-standard-16 | 3.7 h / 1.3 h | Table 11, Section 6.3 |
| `bot-iot-official/`, `bot-iot-official-rerun/` | BoT-IoT full audit with 10-seed falsification; the rerun is at the frozen code | n2-standard-4 / n2-highmem-8 | 2.4 h / 1.0 h | Tables 9, 11 |
| `iot23/` | IoT-23 attempt: a checkpoint and a memory trace only | n2-custom-16 (384 GB) | did not complete (out of memory) | Section 6.1 |
| `cap-sensitivity-glf/` | `validation/cap_sensitivity.py` | n2-standard-16 | 0.8 h | Section 8 |
| `cic-ids2018-split-analysis/` | `validation/batch_split_analysis.py` on all 16,232,943 rows: `homogeneity_test` before and after deduplication, and 10 paired seeds scoring random forest, logistic regression and XGBoost | n2-highmem-16 (16 vCPU, 128 GB) | 3.6 h including one spot preemption | Tables 9, S4, S6; Sections 6.3, 8 |

`cic-ids2018-split-analysis/` is a staged analysis, not an `ids2eval` run: `out/state.json` records
each stage, `out/homogeneity.json` the check's output and threshold grid, `out/seeds/seed_<n>.json`
one paired seed each, and `out/class_sensitive_seeds.json` and `out/model_sensitivity.json` the
summaries merged into `analysis/`. Its cached dataset stayed in the bucket; to rerun, see the
header of `validation/batch_split_analysis.sh` (the job needs offline wheels and a VM without an
external IP).

The CIC-IDS2017 case study of Section 5 runs the separate detection pipeline the case study
describes, not IDS2Eval; its outputs will be listed here when the run completes.
