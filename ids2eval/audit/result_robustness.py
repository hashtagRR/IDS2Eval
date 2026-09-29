"""Result robustness matrix (v2, opt-in).

Every other check here measures a property of the data. This measures
something different: how much a benchmark's headline accuracy moves
across a handful of methodology choices that are each individually
reasonable, random split vs. a session-grouped split, with vs. without
exact duplicates, with vs. without declared identity columns, rather
than assuming a single reported number is the whole story. A result
that barely moves across these conditions is robust to how it was
produced; one that swings widely was measuring the methodology as much
as the attack behavior.

Deliberately reports the full accuracy-by-condition vector rather than
collapsing it into one fragility score: which specific condition moved
the result, and by how much, is the useful information, and a single
number would hide exactly that (the same reasoning class_distribution_
report and every per-class breakdown in this project already follow).

Builds on infrastructure already in place rather than duplicating it:
dataset._random_split/_grouped_split (resplit_falsification), dataset.
dedup (dedup_check), and fit_and_score's column-subset override
(feature_category_ablation_check). Needs dataset.raw_files, like every
other check that builds its own comparison splits from the raw data;
the grouped-split and identity-column conditions are each included only
when the config actually supports them (dataset.group_columns,
schema.id_like_columns), so a minimal config still gets at least the
random-split-vs-dedup comparison.

Every condition's (train, test) pair is built first - relatively cheap next
to the fit itself - so the actual fit_and_score calls can be dispatched
together, concurrently via a thread pool when audit.parallel_checks is set.
"""

from __future__ import annotations

import concurrent.futures

from ..data import dataset, features
from . import _materiality
from ._fit_score import fit_and_score

# Overridable via audit.materiality_thresholds.result_robustness_check ({"warning": .., "flag": ..}).
SPREAD_FLAG_THRESHOLD = 0.15
SPREAD_WARNING_THRESHOLD = 0.08


def check(cfg: dict) -> dict:
    dataset_cfg = cfg["dataset"]
    if not dataset_cfg["raw_files"]:
        return {
            "check": "result_robustness_check", "status": "ok",
            "summary": "requires dataset.raw_files, not applicable to a pre-split train_file/test_file pair",
            "details": {},
        }

    seed = cfg["random_seed"]
    label_col = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(dataset_cfg, seed=seed)

    # name -> (train_df, test_df, cols_override); built up front so the actual fits
    # (the expensive part) can all be dispatched together below.
    pending: dict[str, tuple] = {}
    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg, seed=seed)
    pending["random_split"] = (random_train, random_test, None)

    if dataset_cfg["group_columns"]:
        try:
            grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg, seed=seed)
            pending["grouped_split"] = (grouped_train, grouped_test, None)
        except (ValueError, RuntimeError):
            pass  # same graceful-skip as resplit_falsification when a grouped split can't be built

    deduped_train, deduped_test, dedup_stats = dataset.dedup(random_train.copy(), random_test.copy(), cfg)
    # Only a distinct condition if dedup actually removed something; otherwise it's
    # an identical refit of the random_split condition, not a second data point.
    if (
        dedup_stats["train_rows_raw"] != dedup_stats["train_rows_deduped"]
        or dedup_stats["test_rows_raw"] != dedup_stats["test_rows_deduped"]
    ):
        pending["deduplicated"] = (deduped_train, deduped_test, None)

    id_cols = [c for c in cfg["schema"]["id_like_columns"] if c in random_train.columns]
    if id_cols:
        all_cols = features.feature_columns(random_train, cfg)
        without_ids = [c for c in all_cols if c not in id_cols]
        if without_ids:
            pending["identity_columns_dropped"] = (random_train, random_test, without_ids)

    if len(pending) < 2:
        return {
            "check": "result_robustness_check", "status": "ok",
            "summary": "fewer than two conditions could be built to compare", "details": {},
        }

    def run(name: str) -> tuple[str, float]:
        train_df, test_df, cols = pending[name]
        return name, fit_and_score(train_df, test_df, label_col, cfg, cols=cols, seed=seed)

    if cfg["audit"]["parallel_checks"]:
        max_workers = min(cfg["audit"]["max_parallel_checks"], len(pending))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            conditions = dict(pool.map(run, pending))
    else:
        conditions = dict(run(name) for name in pending)

    worst_condition, worst_acc = min(conditions.items(), key=lambda kv: kv[1])
    best_condition, best_acc = max(conditions.items(), key=lambda kv: kv[1])
    spread = best_acc - worst_acc

    tiers = _materiality.threshold(
        cfg, "result_robustness_check",
        {"warning": SPREAD_WARNING_THRESHOLD, "flag": SPREAD_FLAG_THRESHOLD},
    )
    if spread > tiers["flag"]:
        status = "flag"
    elif spread > tiers["warning"]:
        status = "warning"
    else:
        status = "ok"

    summary = (
        f"accuracy ranges from {worst_acc:.4f} ({worst_condition}) to {best_acc:.4f} "
        f"({best_condition}) across {len(conditions)} conditions, a spread of {spread:.4f}"
    )
    if status != "ok":
        summary += "; the headline result depends on methodology choices as much as the classifier"

    return {
        "check": "result_robustness_check", "status": status, "summary": summary,
        "details": {
            "accuracy_by_condition": conditions, "spread": spread,
            "worst_condition": worst_condition, "best_condition": best_condition,
        },
    }
