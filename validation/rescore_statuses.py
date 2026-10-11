"""Rebuild a run's scorecard under the v0.2.1 status rule, from its archived audit reports.

v0.2.1 adds the not_applicable status: a check that had no input to test (no configured
column, a pre-split dataset where raw files are needed, too few classes or rows) no
longer reports "ok". Every statistic, threshold and ok/warning/flag rule is unchanged,
so a frozen v0.2.0 run does not need to be repeated: each finding whose summary is one
of the no-input summaries below is relabelled not_applicable, and every other finding
keeps its status. The patterns are the exact summaries of the no-input returns in
ids2eval/audit/ (and homogeneity_test's "0 classes tested").

Writes the rescored audit reports, scorecard.json, SCORECARD.md and SCORECARD.html into
the output folder; the input folder is left untouched.

usage: python validation/rescore_statuses.py <run_dir> <out_dir>
"""

import json
import re
import shutil
import sys
from pathlib import Path

from ids2eval.reporting import scorecard

NO_INPUT = re.compile("|".join([
    r"^no schema\.\w+ configured$",
    r"^no id_like_columns configured$",
    r"^no schema\.id_like_columns or schema\.timestamp_column present as a feature",
    r"^none of schema\.feature_categories's columns are present in the loaded data$",
    r"^every declared category covers all features, nothing left to ablate against$",
    r"^requires dataset\.raw_files, not applicable to a pre-split train_file/test_file pair$",
    r"^'.+' not found in the loaded data$",
    r"^fewer than two (distinct scenarios|scenarios with enough rows|conditions could be built|classes have enough rows)",
    r"^scenario '.+' has too few rows or labels to test$",
    r"^skipped, \d+ eligible scenarios exceeds the",
    r"^no scenario pair had enough distinct labels to test$",
    r"^no numeric feature (columns to rank|had both classes present to rank)$",
    r"^no port-like entry in schema\.id_like_columns and/or no proto-like column found",
    r"^not enough rows or classes in either split to test row order",
    r"^no usable timestamp values to test$",
    r"^timestamp column has no usable time span to test$",
    r"^not enough valid timestamps per class to test$",
    r"^no single-feature rule found \(fewer than two classes in the fitted sample\)$",
    r"^audit\.repeated_seed_count \(\d+\) is below the minimum of",
    r"^0 classes tested;",
]))


def rescore(findings: list[dict]) -> list[dict]:
    out = []
    for f in findings:
        if f["status"] == "ok" and NO_INPUT.search(f["summary"]):
            f = {**f, "status": "not_applicable"}
        out.append(f)
    return out


def main(run_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    old = json.loads((run_dir / "scorecard.json").read_text())
    before_path, after_path = run_dir / "audit_report_before.json", run_dir / "audit_report_after.json"
    before = rescore(json.loads(before_path.read_text())) if before_path.exists() else None
    after = rescore(json.loads(after_path.read_text())) if after_path.exists() else None
    fingerprint = {**old["dataset_fingerprint"]}
    cfg = {"dataset": {"name": old["dataset_name"]}}
    if after is not None:
        sc = scorecard.build_scorecard(after, "after", cfg, fingerprint, findings_before=before)
    else:
        sc = scorecard.build_scorecard(before, "before", cfg, fingerprint)
    # Provenance stays the frozen run's: the findings were computed then, only their labels changed.
    sc.update({
        "generated_at": old["generated_at"],
        "ids2eval_version": old["ids2eval_version"],
        "ids2eval_git_commit": old["ids2eval_git_commit"],
        "dedup_effect": old.get("dedup_effect"),
        "status_rule": "v0.2.1 (rescored from the archived audit reports by validation/rescore_statuses.py)",
    })
    for name, findings in (("audit_report_before.json", before), ("audit_report_after.json", after)):
        if findings is not None:
            (out_dir / name).write_text(json.dumps(findings, indent=2))
    (out_dir / "scorecard.json").write_text(json.dumps(sc, indent=2))
    (out_dir / "SCORECARD.md").write_text(scorecard.render_markdown(sc))
    (out_dir / "SCORECARD.html").write_text(scorecard.render_html(sc))
    for f in run_dir.iterdir():
        if f.is_file() and not (out_dir / f.name).exists():
            shutil.copy(f, out_dir / f.name)
    moved = [f["check"] for f in (after or before) if f["status"] == "not_applicable"]
    print(f"{run_dir.name}: {len(moved)} not applicable: {', '.join(moved)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
