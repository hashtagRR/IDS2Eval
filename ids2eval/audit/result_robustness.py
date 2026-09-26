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
"""

from __future__ import annotations

from ..data import dataset, features
from ._fit_score import fit_and_score

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

    label_col = cfg["schema"]["label_column"]
    combined = dataset.load_raw_combined(dataset_cfg)

    conditions: dict[str, float] = {}
    random_train, random_test = dataset._random_split(combined, label_col, dataset_cfg)
    conditions["random_split"] = fit_and_score(random_train, random_test, label_col, cfg)

    if dataset_cfg["group_columns"]:
        try:
            grouped_train, grouped_test = dataset._grouped_split(combined, label_col, dataset_cfg)
            conditions["grouped_split"] = fit_and_score(grouped_train, grouped_test, label_col, cfg)
        except (ValueError, RuntimeError):
            pass  # same graceful-skip as resplit_falsification when a grouped split can't be built

    deduped_train, deduped_test, dedup_stats = dataset.dedup(random_train.copy(), random_test.copy(), cfg)
    # Only a distinct condition if dedup actually removed something; otherwise it's
    # an identical refit of the random_split condition, not a second data point.
    if (
        dedup_stats["train_rows_raw"] != dedup_stats["train_rows_deduped"]
        or dedup_stats["test_rows_raw"] != dedup_stats["test_rows_deduped"]
    ):
        conditions["deduplicated"] = fit_and_score(deduped_train, deduped_test, label_col, cfg)

    id_cols = [c for c in cfg["schema"]["id_like_columns"] if c in random_train.columns]
    if id_cols:
        all_cols = features.feature_columns(random_train, cfg)
        without_ids = [c for c in all_cols if c not in id_cols]
        if without_ids:
            conditions["identity_columns_dropped"] = fit_and_score(
                random_train, random_test, label_col, cfg, cols=without_ids
            )

    if len(conditions) < 2:
        return {
            "check": "result_robustness_check", "status": "ok",
            "summary": "fewer than two conditions could be built to compare", "details": {},
        }

    worst_condition, worst_acc = min(conditions.items(), key=lambda kv: kv[1])
    best_condition, best_acc = max(conditions.items(), key=lambda kv: kv[1])
    spread = best_acc - worst_acc

    if spread > SPREAD_FLAG_THRESHOLD:
        status = "flag"
    elif spread > SPREAD_WARNING_THRESHOLD:
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
