"""Repeated-seed resplit falsification (v2, opt-in).

resplit_falsification (Section 3.5) reports one random-split accuracy and
one grouped-split accuracy, each from a single seed. That single comparison
cannot itself distinguish "this gap is genuinely small" from "a different
seed for either split would show a materially different gap purely from
sampling variance" - exactly the limitation this project's own audit paper
disclosed and left as its most important piece of undone follow-up work.

This check closes that gap by repeating the same random-vs-grouped
comparison across several independent seeds (each seed reshuffles both the
random split and the StratifiedGroupKFold shuffle within the grouped split,
and refits a freshly-seeded RandomForest for each), then reports the mean
drop and a 95% confidence interval, using Student's t-distribution rather
than a normal approximation since n_seeds is deliberately small (5-10, not
hundreds - each additional seed is a full pair of RandomForest refits on
the whole raw dataset).

Each seed is scored on accuracy, balanced accuracy and macro-F1 (see
_metrics), and each metric gets its own interval and verdict; the status is
the most severe verdict among audit.materiality_metrics. The details also
carry each metric's verdict at a range of thresholds (THRESHOLD_SWEEP), the
grouped/random error ratio, and the grouping key's group statistics. Seeds
whose grouped split leaves a class without training or test rows are listed
and called out in the summary; the verdicts are not changed.

Materiality classification compares each CI against the SAME frozen
threshold resplit_falsification itself uses (audit.materiality_thresholds.
repeated_seed_falsification_check, defaulting to resplit_falsification's own
default), via a three-way rule rather than a single point-estimate cutoff:

    material       if the CI's lower bound is still above the threshold
                   (even the most conservative estimate says it matters)
    not material   if the CI's upper bound is below the threshold
                   (even the most generous estimate says it doesn't)
    inconclusive   if the CI straddles the threshold (n_seeds isn't enough
                   to tell, one way or the other - reported as its own
                   outcome, not silently folded into "ok", per this
                   project's own statistical-analysis-plan rule: never
                   infer "no effect" merely because a test isn't
                   significant)

Same preconditions as resplit_falsification: needs dataset.raw_files and
dataset.group_columns, and reloads the raw data itself, so its result
cannot depend on preprocessing.dedup either (see STRUCTURAL_CHECKS).

If audit.parallel_checks is set, the remaining (not yet checkpointed) seeds
run concurrently via a thread pool instead of one at a time - this check is
n_seeds independent full refits, so it's the single biggest reason a config
enabling it alongside only 1-2 other checks can still leave most of a
multi-vCPU VM idle if only the OUTER per-check dispatch were parallelized.
Never combined with checkpoint_path: per-seed checkpointing and concurrent
seeds are mutually exclusive at the config level (audit.checkpoint and
audit.parallel_checks can't both be true) for the same reason run_audit's
outer dispatch keeps them apart - concurrent writers to one checkpoint file
would race.

Accepts an already-loaded `combined` DataFrame so run_audit can share one
load across this, resplit_falsification, and result_robustness_check when
several run together, instead of each reloading the full raw dataset from
disk - a real cost at full scale (a real failure this was built to avoid:
a 70M-row config running all three of these checks was reloading the same
data three times sequentially, contributing to repeated VM-level
instability on a long run). Still loads it itself when called standalone,
so this is purely an optimization, not a behavior change.
"""

from __future__ import annotations

import concurrent.futures
from statistics import mean, stdev

import pandas as pd
from scipy import stats

from ..data import dataset
from . import _checkpoint, _groups, _metrics
from ._fit_score import fit_and_evaluate
from ._status import NOT_APPLICABLE
from .resplit import MATERIAL_DROP_THRESHOLD

DEFAULT_N_SEEDS = 10
MIN_N_SEEDS = 3  # below this, a t-based CI is too unstable to report meaningfully
# Thresholds at which every metric's verdict is also reported, so a reader can
# apply their own materiality standard without rerunning anything.
THRESHOLD_SWEEP = (0.005, 0.01, 0.02, 0.05)
_CHECK_NAME = "repeated_seed_falsification_check"


def _interval(values: list[float]) -> tuple[float, float, float]:
    """Mean and two-sided 95% t-interval (n - 1 degrees of freedom), suited to
    this few independent repeats; a normal approximation would understate the
    uncertainty at this sample size."""
    n = len(values)
    centre = mean(values)
    margin = stats.t.ppf(0.975, df=n - 1) * stdev(values) / (n ** 0.5)
    return centre, centre - margin, centre + margin


def check(
    cfg: dict, n_seeds: int | None = None, checkpoint_path: str | None = None,
    combined: pd.DataFrame | None = None,
) -> dict:
    dataset_cfg = cfg["dataset"]
    if n_seeds is None:
        n_seeds = cfg["audit"]["repeated_seed_count"]
    if n_seeds < MIN_N_SEEDS:
        return {
            "check": _CHECK_NAME, "status": NOT_APPLICABLE,
            "summary": f"audit.repeated_seed_count ({n_seeds}) is below the minimum of "
                       f"{MIN_N_SEEDS} needed for a meaningful confidence interval",
            "details": {},
        }

    label_col = cfg["schema"]["label_column"]

    # Resume from any seeds already checkpointed (e.g. a prior run of this same
    # checkpoint_path that crashed partway through) rather than redoing them -
    # this check alone can dominate a full-scale run's cost, so losing all
    # progress to a mid-sweep crash is exactly the failure mode worth avoiding.
    # Only per-metric entries are reused; a bare accuracy drop saved by a version
    # before 0.3.0 lacks the other metrics, so that seed is refitted.
    completed = _checkpoint.get_seed_progress(checkpoint_path, _CHECK_NAME) if checkpoint_path else {}
    per_seed: list[dict] = []
    for s in range(n_seeds):
        entry = completed.get(s)
        if not (isinstance(entry, dict) and all(m in entry for m in _metrics.METRICS)):
            break
        per_seed.append(entry)
    remaining_seeds = list(range(len(per_seed), n_seeds))

    if combined is None and remaining_seeds:
        combined = dataset.load_raw_combined(dataset_cfg, seed=cfg["random_seed"])

    def run_seed(seed: int) -> dict:
        # Scored one split at a time, not both built up front - see resplit.check's
        # own comment: holding combined plus both split pairs at once is the
        # dominant memory cost at full scale, and this runs n_seeds times.
        random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
        random_m = fit_and_evaluate(random_train, random_test, label_col, cfg, seed=seed).metrics
        del random_train, random_test

        grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg, seed=seed)
        grouped_m = fit_and_evaluate(grouped_train, grouped_test, label_col, cfg, seed=seed).metrics
        class_loss = _groups.class_support(grouped_train[label_col], grouped_test[label_col])
        del grouped_train, grouped_test
        entry = {m: random_m[m] - grouped_m[m] for m in _metrics.METRICS}
        entry["grouped_class_support"] = class_loss
        entry["random_accuracy"] = random_m["accuracy"]
        entry["grouped_accuracy"] = grouped_m["accuracy"]
        return entry

    if cfg["audit"]["parallel_checks"] and not checkpoint_path and len(remaining_seeds) > 1:
        max_workers = min(cfg["audit"]["max_parallel_checks"], len(remaining_seeds))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            # map preserves input order in its results regardless of completion order,
            # so per_seed stays seed-ordered the same as the sequential path.
            per_seed.extend(pool.map(run_seed, remaining_seeds))
    else:
        for seed in remaining_seeds:
            entry = run_seed(seed)
            per_seed.append(entry)
            if checkpoint_path:
                _checkpoint.save_seed_progress(checkpoint_path, _CHECK_NAME, seed, entry)

    thresholds = _metrics.thresholds(cfg, _CHECK_NAME, MATERIAL_DROP_THRESHOLD)
    by_metric, verdicts = {}, {}
    for m in _metrics.METRICS:
        drops = [entry[m] for entry in per_seed]
        centre, low, high = _interval(drops)
        verdicts[m] = _metrics.interval_verdict(low, high, thresholds[m])
        by_metric[m] = {
            "drops_by_seed": drops, "mean_drop": centre, "ci_95": [low, high],
            "threshold": thresholds[m], "verdict": verdicts[m],
            "verdict_by_threshold": {
                str(t): _metrics.interval_verdict(low, high, t) for t in THRESHOLD_SWEEP
            },
        }
    status = _metrics.combined_status(verdicts, cfg)

    ratios = [
        r for r in (_metrics.error_ratio(e["random_accuracy"], e["grouped_accuracy"])
                    for e in per_seed if "random_accuracy" in e)
        if r is not None
    ]
    acc = by_metric["accuracy"]
    words = {"flag": "material", "ok": "not material", "warning": "inconclusive"}
    summary = (
        f"grouped-split drop across {n_seeds} seeds, mean [95% CI]: accuracy "
        f"{acc['mean_drop']:+.4f} [{acc['ci_95'][0]:+.4f}, {acc['ci_95'][1]:+.4f}], balanced accuracy "
        f"{by_metric['balanced_accuracy']['mean_drop']:+.4f} "
        f"[{by_metric['balanced_accuracy']['ci_95'][0]:+.4f}, {by_metric['balanced_accuracy']['ci_95'][1]:+.4f}], "
        f"macro-F1 {by_metric['macro_f1']['mean_drop']:+.4f} "
        f"[{by_metric['macro_f1']['ci_95'][0]:+.4f}, {by_metric['macro_f1']['ci_95'][1]:+.4f}]; "
        f"{_metrics.describe(verdicts)}; overall {words[status]} on {', '.join(cfg['audit']['materiality_metrics'])}"
    )
    details = {
        "n_seeds": n_seeds,
        # Accuracy fields kept under their pre-0.3.0 names for existing readers.
        "drops_by_seed": acc["drops_by_seed"],
        "mean_drop": acc["mean_drop"],
        "ci_95": acc["ci_95"],
        "materiality_threshold": thresholds["accuracy"],
        "material": {"flag": True, "ok": False, "warning": None}[status],
        "by_metric": by_metric,
        "materiality_metrics": list(cfg["audit"]["materiality_metrics"]),
        "mean_error_ratio": mean(ratios) if ratios else None,
    }
    if combined is not None:
        details["group_stats"] = _groups.group_stats(combined, dataset_cfg["group_columns"])
    lossy = [s for s, e in enumerate(per_seed)
             if _groups.describe_class_loss(e.get("grouped_class_support", {"missing_from_train": [],
                                                                             "missing_from_test": []}))]
    details["seeds_with_grouped_class_loss"] = lossy
    if lossy:
        details["grouped_class_support_by_seed"] = {
            s: per_seed[s]["grouped_class_support"] for s in lossy
        }
        summary += (
            f"; CAUTION, in {len(lossy)} of {n_seeds} seeds the grouped split leaves a class without "
            "training or test rows (see grouped_class_support_by_seed), so those seeds' scores do not "
            "measure that class"
        )
    return {"check": _CHECK_NAME, "status": status, "summary": summary, "details": details}
