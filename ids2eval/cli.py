"""CLI entrypoint: config -> dataset split -> audit -> preprocessing -> benchmark.

    python -m ids2eval --config my_config.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from . import dataset
from .audit import run_audit
from .benchmark import run_benchmark
from .config import load_config

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
    train_df, test_df = dataset.load_split(cfg)
    logger.info("Split: train=%d rows, test=%d rows", len(train_df), len(test_df))

    if not args.skip_audit:
        # Must run before dedup — dedup_check reports duplication already
        # present in the split, and dataset.dedup() would remove it first.
        findings = run_audit(train_df, test_df, cfg)
        report_path = output_dir / "audit_report.json"
        report_path.write_text(json.dumps(findings, indent=2, default=_json_default))
        logger.info("Audit report written to %s", report_path)
        for f in findings:
            logger.info("[%s] %s: %s", f["status"].upper(), f["check"], f["summary"])

    if cfg["preprocessing"]["dedup"]:
        train_df, test_df, dedup_stats = dataset.dedup(train_df, test_df, cfg)
        logger.info("Dedup: %s", dedup_stats)

    if cfg["output"]["save_preprocessed"]:
        fmt = cfg["output"]["format"]
        for name, df in [("train", train_df), ("test", test_df)]:
            path = output_dir / f"{name}.{fmt}"
            if fmt == "parquet":
                df.to_parquet(path, index=False)
            else:
                df.to_csv(path, index=False)
            logger.info("Wrote %s", path)

    if not args.skip_benchmark:
        results_df = run_benchmark(train_df, test_df, cfg)
        results_path = output_dir / "benchmark_results.csv"
        results_df.to_csv(results_path, index=False)
        logger.info("Benchmark results written to %s", results_path)
        logger.info("\n%s", results_df.to_string(index=False))


if __name__ == "__main__":
    main()
