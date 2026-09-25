"""CLI entrypoint: config -> dataset split -> audit -> preprocessing -> benchmark.

    python -m ids2eval --config my_config.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from .audit import STRUCTURAL_CHECKS, run_audit
from .config import load_config
from .data import cache, dataset
from .data.label_grouping import apply_attack_type_mapping
from .modeling.benchmark import run_benchmark
from .reporting import drift, run_manager, scorecard

logger = logging.getLogger(__name__)


def _json_default(obj):
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _write_findings(path: Path, findings: list[dict]) -> None:
    path.write_text(json.dumps(findings, indent=2, default=_json_default))
    logger.info("Audit report written to %s", path)
    for f in findings:
        logger.info("[%s] %s: %s", f["status"].upper(), f["check"], f["summary"])


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IDS2Eval: audit + benchmark an IDS dataset")
    parser.add_argument("--config", required=True, help="Path to a YAML config file")
    parser.add_argument("--skip-audit", action="store_true", help="Skip the data-quality audit checks")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip classifier benchmarking")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    cfg = load_config(args.config)

    output_dir = Path(cfg["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading dataset '%s'", cfg["dataset"]["name"])
    cached = cache.try_load(cfg)
    if cached is not None:
        train_df, test_df = cached
    else:
        train_df, test_df = dataset.load_split(cfg)
        # Applied before audit/benchmarking so both see the collapsed
        # categories consistently, not just the final benchmark stage.
        train_df, test_df = apply_attack_type_mapping(train_df, test_df, cfg)
        dataset.validate_loaded(train_df, test_df, cfg)
        cache.save(train_df, test_df, cfg)
    logger.info("Split: train=%d rows, test=%d rows", len(train_df), len(test_df))

    # A load-phase crash has no run_dir to report status into - there's no
    # run to speak of yet, not even a failed one, until loading succeeds.
    run_dir = run_manager.create_run_dir(output_dir)
    run_manager.write_environment_info(run_dir)
    run_manager.write_resolved_config(run_dir, cfg)
    fingerprint = run_manager.write_dataset_fingerprint(run_dir, train_df, test_df, cfg)
    logger.info("Run artifacts: %s", run_dir)

    stage = "audit_before"
    try:
        if not args.skip_audit:
            # Must run before dedup. dedup_check reports duplication already
            # present in the split, and dataset.dedup() would remove it first.
            stage = "audit_before"
            findings_before = run_audit(train_df, test_df, cfg)
            _write_findings(run_dir / "audit_report_before.json", findings_before)

        if cfg["preprocessing"]["dedup"]:
            stage = "dedup"
            train_df, test_df, dedup_stats = dataset.dedup(train_df, test_df, cfg)
            logger.info("Dedup: %s", dedup_stats)

            if not args.skip_audit:
                # Full suite again on the cleaned data, by explicit choice, so a
                # claim like "12% duplicate leakage before, 0% after" is backed
                # by two real runs rather than assumed from the dedup stats alone.
                # STRUCTURAL_CHECKS are skipped here and copied from the before-pass
                # instead: their result can't depend on dedup (known_issue_lookup
                # looks at dataset.name, schema_fingerprint_check at column names,
                # resplit_falsification reloads the raw data itself), so recomputing
                # them - resplit_falsification's two RandomForest fits included -
                # would be pure wasted work, not a second real measurement.
                stage = "audit_after"
                recomputed = {f["check"]: f for f in run_audit(train_df, test_df, cfg, skip=STRUCTURAL_CHECKS)}
                reused = {f["check"]: f for f in findings_before if f["check"] in STRUCTURAL_CHECKS}
                # dict order follows findings_before's schema order, not recompute order.
                findings_after = [(recomputed | reused)[f["check"]] for f in findings_before]
                _write_findings(run_dir / "audit_report_after.json", findings_after)

        if not args.skip_audit:
            # Reflects whichever findings describe the data actually shipped
            # in this run - the post-dedup pass if dedup ran, otherwise the
            # only pass there was.
            stage = "scorecard"
            final_findings = findings_after if cfg["preprocessing"]["dedup"] else findings_before
            final_audit_stage = "after" if cfg["preprocessing"]["dedup"] else "before"
            sc = scorecard.build_scorecard(
                final_findings, final_audit_stage, cfg, fingerprint,
                findings_before=findings_before if final_audit_stage == "after" else None,
            )

            previous_run_dir = drift.find_previous_run(output_dir, run_dir)
            if previous_run_dir is not None:
                comparison = drift.compare(sc, previous_run_dir)
                if comparison is not None:
                    sc["previous_run_comparison"] = comparison
                    if comparison["changed_checks"]:
                        logger.info(
                            "Compared to %s: %d check(s) changed status",
                            comparison["previous_run"], len(comparison["changed_checks"]),
                        )

            has_plot = cfg["output"]["write_scorecard_plot"]
            if has_plot:
                from .reporting import scorecard_plot
                scorecard_plot.render(sc, final_findings, run_dir / "scorecard.pdf", run_dir / "scorecard.png")
                logger.info("Scorecard plot written to %s / .png", run_dir / "scorecard.pdf")

            run_manager.write_scorecard(
                run_dir, sc, scorecard.render_markdown(sc, has_plot=has_plot), scorecard.render_html(sc)
            )
            logger.info("Scorecard: %s -> %s", sc["overall_status"], run_dir / "scorecard.json")

        if cfg["output"]["save_preprocessed"]:
            stage = "save_preprocessed"
            fmt = cfg["output"]["format"]
            for name, df in [("train", train_df), ("test", test_df)]:
                path = run_dir / f"{name}.{fmt}"
                if fmt == "parquet":
                    df.to_parquet(path, index=False)
                else:
                    df.to_csv(path, index=False)
                logger.info("Wrote %s", path)

        if not args.skip_benchmark:
            stage = "benchmark"
            results_df, extras = run_benchmark(train_df, test_df, cfg)
            results_path = run_dir / "benchmark_results.csv"
            results_df.to_csv(results_path, index=False)
            details_path = run_dir / "benchmark_details.json"
            details_path.write_text(json.dumps(extras, indent=2, default=_json_default))
            logger.info("Benchmark results written to %s", results_path)
            logger.info("Per-classifier detail (confusion matrix, per-class report, "
                        "feature importance, best params) written to %s", details_path)
            logger.info("\n%s", results_df.to_string(index=False))

        run_manager.write_run_status(run_dir, status="completed")
    except Exception as e:
        run_manager.write_run_status(run_dir, status="failed", failed_stage=stage, error=str(e))
        raise
    finally:
        run_manager.cleanup_old_runs(output_dir, cfg["output"]["keep_runs"])


if __name__ == "__main__":
    main()
