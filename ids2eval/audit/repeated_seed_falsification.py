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

Materiality classification compares the CI against the SAME frozen
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
"""

from __future__ import annotations

from statistics import mean, stdev

from scipy import stats

from ..data import dataset
from . import _checkpoint, _materiality
from ._fit_score import fit_and_score
from .resplit import MATERIAL_DROP_THRESHOLD

DEFAULT_N_SEEDS = 10
MIN_N_SEEDS = 3  # below this, a t-based CI is too unstable to report meaningfully
_CHECK_NAME = "repeated_seed_falsification_check"


def check(cfg: dict, n_seeds: int | None = None, checkpoint_path: str | None = None) -> dict:
    dataset_cfg = cfg["dataset"]
    if n_seeds is None:
        n_seeds = cfg["audit"]["repeated_seed_count"]
    if n_seeds < MIN_N_SEEDS:
        return {
            "check": _CHECK_NAME, "status": "ok",
            "summary": f"audit.repeated_seed_count ({n_seeds}) is below the minimum of "
                       f"{MIN_N_SEEDS} needed for a meaningful confidence interval",
            "details": {},
        }

    label_col = cfg["schema"]["label_column"]

    # Resume from any seeds already checkpointed (e.g. a prior run of this same
    # checkpoint_path that crashed partway through) rather than redoing them -
    # this check alone can dominate a full-scale run's cost, so losing all
    # progress to a mid-sweep crash is exactly the failure mode worth avoiding.
    completed: dict[int, float] = (
        _checkpoint.get_seed_progress(checkpoint_path, _CHECK_NAME) if checkpoint_path else {}
    )
    drops = [completed[s] for s in sorted(completed) if s < n_seeds]
    start_seed = len(drops)

    combined = dataset.load_raw_combined(dataset_cfg) if start_seed < n_seeds else None
    for seed in range(start_seed, n_seeds):
        random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
        grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg, seed=seed)
        random_acc = fit_and_score(random_train, random_test, label_col, cfg, seed=seed)
        grouped_acc = fit_and_score(grouped_train, grouped_test, label_col, cfg, seed=seed)
        drop = random_acc - grouped_acc
        drops.append(drop)
        if checkpoint_path:
            _checkpoint.save_seed_progress(checkpoint_path, _CHECK_NAME, seed, drop)

    mean_drop = mean(drops)
    sample_std = stdev(drops)  # n_seeds >= MIN_N_SEEDS >= 2, safe for stdev's ddof=1
    # Two-sided 95% CI for the mean via the t-distribution (n_seeds - 1 degrees of
    # freedom), appropriate for this few independent repeats rather than a normal
    # approximation that would understate the uncertainty at this sample size.
    margin = stats.t.ppf(0.975, df=n_seeds - 1) * sample_std / (n_seeds ** 0.5)
    ci_low, ci_high = mean_drop - margin, mean_drop + margin

    threshold = _materiality.threshold(
        cfg, "repeated_seed_falsification_check", MATERIAL_DROP_THRESHOLD,
    )
    if ci_low > threshold:
        material, status = True, "flag"
        verdict = (
            f"material: even the most conservative estimate in the 95% CI ({ci_low:+.4f}) "
            f"exceeds the {threshold:+.4f} materiality threshold"
        )
    elif ci_high < threshold:
        material, status = False, "ok"
        verdict = (
            f"not material: even the most generous estimate in the 95% CI ({ci_high:+.4f}) "
            f"stays below the {threshold:+.4f} materiality threshold"
        )
    else:
        material, status = None, "warning"
        verdict = (
            f"inconclusive: the 95% CI [{ci_low:+.4f}, {ci_high:+.4f}] straddles the "
            f"{threshold:+.4f} materiality threshold; {n_seeds} seeds aren't enough to "
            "tell whether this gap is real or sampling noise"
        )

    return {
        "check": _CHECK_NAME,
        "status": status,
        "summary": (
            f"grouped-split accuracy drop across {n_seeds} seeds: mean={mean_drop:+.4f}, "
            f"95% CI=[{ci_low:+.4f}, {ci_high:+.4f}]; {verdict}"
        ),
        "details": {
            "n_seeds": n_seeds,
            "drops_by_seed": drops,
            "mean_drop": mean_drop,
            "ci_95": [ci_low, ci_high],
            "materiality_threshold": threshold,
            "material": material,
        },
    }
