"""Data-quality audit checks: Paper 1's methodology as reusable code.

v1 checks need no external reference data; v2 checks (synthetic_realism_check,
cross_dataset_drift_check) need audit.reference_dataset, and known_issue_lookup
is a curated per-dataset lookup table needing neither.

Each check function returns a Finding dict: {check, status, summary, details}.
status is one of "ok" (nothing notable), "warning" (worth a human look), or
"flag" (a specific, checkable signature of a real data-quality problem).

STRUCTURAL_CHECKS are checks whose result cannot depend on
preprocessing.dedup: known_issue_lookup looks only at dataset.name,
schema_fingerprint_check only at column names (dedup removes rows, never
columns), and resplit_falsification/scenario_holdout_falsification/
cross_capture_matrix_check/result_robustness_check all reload the raw
data themselves and never look at the train_df/test_df they're passed.
Run once, on the raw data; run_audit's caller (cli.py)
reuses that result instead of recomputing an answer that is guaranteed
identical the second time.
"""

from __future__ import annotations

import concurrent.futures
import logging
import time

import pandas as pd

from ..data import dataset
from . import (
    _checkpoint,
    artifact_sensitivity,
    class_distribution,
    cross_capture_matrix,
    cross_dataset_drift,
    data_integrity,
    dedup,
    feature_auc_ranking,
    feature_category_ablation,
    flow_group_leakage,
    homogeneity,
    identity_columns,
    known_issues,
    label_conflict,
    leakage,
    near_duplicate_class,
    one_rule,
    port_protocol_shortcut,
    repeated_seed_falsification,
    resplit,
    result_robustness,
    row_order_leakage,
    scenario_holdout,
    schema_fingerprint,
    seed_sensitivity,
    synthetic_realism,
    temporal_leakage,
    temporal_realism,
)

STRUCTURAL_CHECKS = frozenset({
    "known_issue_lookup", "schema_fingerprint_check", "resplit_falsification",
    "scenario_holdout_falsification", "cross_capture_matrix_check", "result_robustness_check",
    "repeated_seed_falsification_check",
})

# A strict subset of STRUCTURAL_CHECKS: checks that report a documented, curated fact
# about the dataset or the tool that extracted it (a published labelling error, a
# known-buggy extractor), rather than measuring something about this run's actual
# data. resplit_falsification is structural too, but it measures this run's own split
# methodology and IS actionable (switch dataset.split_mode to "grouped"), so it stays
# out of this set and is reported alongside the other audit checks, not here.
KNOWN_ISSUE_CHECKS = frozenset({"known_issue_lookup", "schema_fingerprint_check"})

# Evidence basis for a check's result, fixed per check name, not computed per
# run: a citation needs a consistent answer to "how sure is this" for the
# same check every time, not a judgment that could vary run to run.
# "documented": a citation lookup against dataset.name or column names, not
# computed from this run's data at all.
# "direct-experiment": an actual counterfactual refit and comparison.
# "statistical": a threshold or hypothesis test against this run's data,
# with no independent corroboration. The default for anything not listed.
# A fourth level, "cross-corroborated", is not a per-check label: it applies
# only when homogeneity_test and resplit_falsification both flag on the
# same run, and is computed once at scorecard-build time from those two
# already-computed statuses (see ids2eval.reporting.scorecard).
EVIDENCE_LEVEL = {
    "known_issue_lookup": "documented",
    "schema_fingerprint_check": "documented",
    "resplit_falsification": "direct-experiment",
    "scenario_holdout_falsification": "direct-experiment",
    "cross_capture_matrix_check": "direct-experiment",
    "feature_category_ablation_check": "direct-experiment",
    "artifact_sensitivity_check": "direct-experiment",
    "result_robustness_check": "direct-experiment",
    "repeated_seed_falsification_check": "direct-experiment",
}
DEFAULT_EVIDENCE_LEVEL = "statistical"

logger = logging.getLogger(__name__)


def run_audit(
    train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict, skip: frozenset[str] = frozenset(),
    checkpoint_path: str | None = None,
) -> list[dict]:
    """Run every audit check enabled in cfg['audit'] and not in `skip`, in schema order.

    Call this on the split BEFORE preprocessing.dedup is applied.
    dedup_check reports duplication already present in train_df/test_df,
    if the caller already deduplicated, it will always report zero.

    `skip` exists for the caller to omit STRUCTURAL_CHECKS on a second call
    with the same cfg (e.g. cli.py's after-dedup pass) - their answer can't
    change, so recomputing them (including resplit_falsification's two
    RandomForest fits) would be pure wasted work.

    Runs sequentially by default. If audit.parallel_checks is set, enabled
    checks instead run concurrently (capped at audit.max_parallel_checks) via
    a thread pool - safe because no check mutates train_df/test_df, only
    reads them. The returned list is always in the same schema order either
    way; only execution order, not the caller-visible result, changes.
    Off by default because several checks running at once means several may
    hold their own encoded feature matrix/RandomForest fit in memory
    simultaneously rather than one at a time, raising peak memory versus the
    sequential default.

    resplit_falsification, result_robustness_check, and repeated_seed_
    falsification_check each need the full raw dataset (not just train_df/
    test_df) and would otherwise each reload it independently - loaded once
    here and shared across whichever of the three are enabled, since that
    reload is a real, serious cost at full scale (see each check's own
    docstring for the real failure this was built to avoid).

    checkpoint_path, if given, persists each check's finding to a local JSON
    file as soon as it's computed and skips recomputing a check whose result
    is already there - so a crash partway through a long run only redoes the
    remaining checks on the next call with the same path. Mutually exclusive
    with parallel_checks (validated in config.py): concurrent checks writing
    to one checkpoint file would race. repeated_seed_falsification_check
    additionally checkpoints its own per-seed progress via this same path,
    since it alone can dominate a full-scale run's cost.
    """
    audit_cfg = cfg["audit"]
    seed = cfg["random_seed"]
    dataset_cfg = cfg["dataset"]

    # resplit_falsification, result_robustness_check, and repeated_seed_falsification_check
    # each independently reload the full raw dataset when called standalone - fine at small
    # scale, but a real, serious cost at full scale: a real failure hit running all three
    # together against a 70M-row dataset, where each ~45-70 minute reload compounded into
    # repeated VM-level instability on a run that redundantly reloaded the same data three
    # times sequentially. Loaded once here and passed to whichever of the three are enabled.
    _raw_reload_checks = ("resplit_falsification", "result_robustness_check", "repeated_seed_falsification_check")
    shared_combined = None
    if dataset_cfg["raw_files"] and any(
        audit_cfg[name] and name not in skip for name in _raw_reload_checks
    ):
        shared_combined = dataset.load_raw_combined(dataset_cfg, seed=seed)

    # Each entry is (check_name, thunk). Building the full ordered list up front - rather
    # than appending each finding immediately - lets the dispatch loop below run these
    # independently (they only read train_df/test_df, never mutate them) either in
    # schema order (default) or concurrently, while the OUTPUT list always comes back in
    # this same schema order regardless of which mode ran or which thunk finished first.
    pending: list[tuple[str, object]] = []

    def add(name: str, thunk) -> None:
        if audit_cfg[name] and name not in skip:
            pending.append((name, thunk))

    add("dedup_check", lambda: dedup.check(train_df, test_df, cfg))
    add("label_conflict_check", lambda: label_conflict.check(train_df, test_df, cfg))
    add("near_duplicate_class_check", lambda: near_duplicate_class.check(train_df, cfg))
    add("leakage_screen", lambda: leakage.check(train_df, test_df, cfg, seed=seed))
    add("one_rule_check", lambda: one_rule.check(train_df, test_df, cfg, seed=seed))
    add("feature_auc_ranking_check", lambda: feature_auc_ranking.check(train_df, cfg))
    add("identity_column_flag", lambda: identity_columns.check_predictive_power(train_df, test_df, cfg))
    add("port_protocol_shortcut_check", lambda: port_protocol_shortcut.check(train_df, test_df, cfg))
    add("temporal_leakage_check", lambda: temporal_leakage.check(train_df, test_df, cfg))
    add("temporal_realism_check", lambda: temporal_realism.check(train_df, cfg))
    add("flow_group_leakage_check", lambda: flow_group_leakage.check(train_df, test_df, cfg))
    add("row_order_leakage_check", lambda: row_order_leakage.check(train_df, test_df, cfg))
    add("homogeneity_test", lambda: homogeneity.check(train_df, test_df, cfg))
    add("resplit_falsification", lambda: resplit.check(cfg, seed=seed, combined=shared_combined))
    add("scenario_holdout_falsification", lambda: scenario_holdout.check(cfg))
    add("class_distribution_report", lambda: class_distribution.check(train_df, test_df, cfg))
    add("low_cardinality_warning", lambda: identity_columns.check_cardinality(train_df, cfg))
    add("schema_fingerprint_check", lambda: schema_fingerprint.check(train_df, cfg))
    add("data_integrity_check", lambda: data_integrity.check(train_df, cfg))
    add("synthetic_realism_check", lambda: synthetic_realism.check(train_df, cfg))
    add("cross_dataset_drift_check", lambda: cross_dataset_drift.check(train_df, test_df, cfg))
    add("cross_capture_matrix_check", lambda: cross_capture_matrix.check(cfg))
    add("feature_category_ablation_check", lambda: feature_category_ablation.check(train_df, test_df, cfg))
    add("artifact_sensitivity_check", lambda: artifact_sensitivity.check(train_df, test_df, cfg))
    add("result_robustness_check", lambda: result_robustness.check(cfg, combined=shared_combined))
    add("known_issue_lookup", lambda: known_issues.check(train_df, cfg))
    add("seed_sensitivity_check", lambda: seed_sensitivity.check(train_df, test_df, cfg))
    add(
        "repeated_seed_falsification_check",
        lambda: repeated_seed_falsification.check(
            cfg, checkpoint_path=checkpoint_path, combined=shared_combined,
        ),
    )

    # One log line per check: some take minutes on a large dataset, and
    # without these a run (and the dashboard's live log) looks frozen.
    total = len(pending)

    def done(i: int, name: str, result: dict, started: float, note: str = "") -> None:
        logger.info("Audit check %d/%d done: %s -> %s (%.1fs%s)", i, total, name,
                    (result or {}).get("status", "?"), time.monotonic() - started, note)

    if not audit_cfg["parallel_checks"]:
        results = []
        for i, (name, thunk) in enumerate(pending, 1):
            started = time.monotonic()
            cached = _checkpoint.get_check(checkpoint_path, name) if checkpoint_path else None
            if cached is None:
                logger.info("Audit check %d/%d: %s ...", i, total, name)
            result = cached if cached is not None else thunk()
            if checkpoint_path and cached is None:
                _checkpoint.save_check(checkpoint_path, name, result)
            done(i, name, result, started, ", from checkpoint" if cached is not None else "")
            results.append(result)
        return results

    max_workers = min(audit_cfg["max_parallel_checks"], len(pending)) or 1
    logger.info("Audit: running %d checks, up to %d at a time", total, max_workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        started = time.monotonic()
        futures = [pool.submit(thunk) for _, thunk in pending]
        names = {f: name for f, (name, _) in zip(futures, pending, strict=True)}
        for i, f in enumerate(concurrent.futures.as_completed(futures), 1):
            if f.exception() is None:
                done(i, names[f], f.result(), started, " since the batch started")
        return [f.result() for f in futures]
