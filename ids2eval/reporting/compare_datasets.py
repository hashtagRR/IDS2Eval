"""Two-dataset equivalence comparison.

Answers a question no single-dataset audit can: are these two configs,
both claiming to load "the same" dataset (an official release and a
third-party mirror, say), actually equivalent? Loads both, computes
each one's fingerprint (run_manager.compute_dataset_fingerprint), and
compares schema, row counts, label distribution, and content.

Not a run_audit check: this compares two DATASETS, not one dataset's
train against its own test, and needs two configs rather than one, a
different enough shape to be its own CLI subcommand
(`ids2eval compare-datasets a.yaml b.yaml`) rather than an audit
finding. Each dataset's own train/test split can use a different
split_ratio or split_mode, so a train-vs-train, test-vs-test content
hash comparison alone could report a mismatch that's really just a
different split of identical underlying data; a combined (train+test
concatenated) hash catches that case, alongside the split-specific
hashes for detail.
"""

from __future__ import annotations

import pandas as pd

from ..config import load_config
from ..data import dataset
from . import run_manager


def _combined_label_counts(fingerprint: dict) -> dict:
    counts: dict[str, int] = {}
    for source in ("train_class_distribution", "test_class_distribution"):
        for label, count in fingerprint[source].items():
            counts[label] = counts.get(label, 0) + count
    return counts


def compare(config_path_a: str, config_path_b: str) -> dict:
    cfg_a = load_config(config_path_a)
    cfg_b = load_config(config_path_b)
    train_a, test_a = dataset.load_split(cfg_a)
    train_b, test_b = dataset.load_split(cfg_b)

    fp_a = run_manager.compute_dataset_fingerprint(train_a, test_a, cfg_a)
    fp_b = run_manager.compute_dataset_fingerprint(train_b, test_b, cfg_b)

    combined_hash_a = run_manager.content_hash(pd.concat([train_a, test_a], ignore_index=True))
    combined_hash_b = run_manager.content_hash(pd.concat([train_b, test_b], ignore_index=True))

    labels_a = _combined_label_counts(fp_a)
    labels_b = _combined_label_counts(fp_b)

    return {
        "dataset_a": cfg_a["dataset"]["name"],
        "dataset_b": cfg_b["dataset"]["name"],
        "schema_match": set(fp_a["columns"]) == set(fp_b["columns"]),
        "columns_only_in_a": sorted(set(fp_a["columns"]) - set(fp_b["columns"])),
        "columns_only_in_b": sorted(set(fp_b["columns"]) - set(fp_a["columns"])),
        "row_count_a": fp_a["train_rows"] + fp_a["test_rows"],
        "row_count_b": fp_b["train_rows"] + fp_b["test_rows"],
        "row_count_match": (fp_a["train_rows"] + fp_a["test_rows"]) == (fp_b["train_rows"] + fp_b["test_rows"]),
        "label_distribution_a": labels_a,
        "label_distribution_b": labels_b,
        "label_distribution_match": labels_a == labels_b,
        "combined_content_match": combined_hash_a == combined_hash_b,
    }


def render_report(result: dict) -> str:
    def verdict(matched: bool, hard: bool = False) -> str:
        return "PASS" if matched else ("FAIL" if hard else "WARN")

    lines = [
        f"Dataset A: {result['dataset_a']}",
        f"Dataset B: {result['dataset_b']}",
        "",
        f"Schema match          {verdict(result['schema_match'], hard=True)}",
        f"Row count match       {verdict(result['row_count_match'])}",
        f"Label distribution    {verdict(result['label_distribution_match'])}",
        f"Combined content      {verdict(result['combined_content_match'], hard=True)}",
    ]

    if not result["schema_match"]:
        if result["columns_only_in_a"]:
            lines.append(f"  columns only in A: {result['columns_only_in_a']}")
        if result["columns_only_in_b"]:
            lines.append(f"  columns only in B: {result['columns_only_in_b']}")
    if not result["row_count_match"]:
        lines.append(f"  A: {result['row_count_a']:,} rows, B: {result['row_count_b']:,} rows")
    if not result["label_distribution_match"]:
        lines.append(f"  A: {result['label_distribution_a']}")
        lines.append(f"  B: {result['label_distribution_b']}")

    # combined_content_match, when true, already means the two datasets' full row
    # sets are identical, which implies matching row counts and label distribution
    # too - those two fields stay useful for diagnosing WHERE a mismatch is when
    # combined_content_match is false, not as a separate verdict branch here.
    lines.append("")
    if result["schema_match"] and result["combined_content_match"]:
        lines.append("Equivalent: same schema, row counts, label distribution, and content.")
    else:
        lines.append("Likely non-equivalent dataset versions.")
    return "\n".join(lines)
