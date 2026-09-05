"""Known-issue lookup (v2, opt-in) — curated per-dataset documented problems.

Unlike schema_fingerprint_check (which matches the *extractor tool*'s
column-naming signature regardless of dataset), this matches on
dataset.name directly and surfaces problems specific to that dataset —
curation work, not a new algorithm. Needs no reference_dataset.

Extend KNOWN_ISSUES as more curated, citable findings are gathered.
Matching is substring-based against a lowercased dataset.name so
"cic-ids2018", "CIC_IDS2018", and "cic2018" all resolve the same way.
"""

from __future__ import annotations

import pandas as pd

KNOWN_ISSUES = {
    "cic-ids2018": [
        {
            "issue": "The 2018-02-23 day-file's Brute-Force-Web/Brute-Force-XSS rows "
                     "are approximately 41% mislabeled (ground-truth labeling error, "
                     "not an extraction or pipeline bug).",
            "citation": "Liu et al. 2022, IEEE CNS",
        },
    ],
    "unsw-nb15": [
        {
            "issue": "Some redistributions invert the UNSW_NB15_training-set.csv/"
                     "testing-set.csv file-name-to-content mapping relative to the "
                     "dataset's documented convention (82,332 vs. 175,341 rows) — "
                     "verify against the published per-attack-category counts before "
                     "trusting file names.",
            "citation": "Independently verified in this project's own audit methodology",
        },
    ],
}


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    name = (cfg["dataset"]["name"] or "").strip().lower()
    matches = [issue for key, issues in KNOWN_ISSUES.items() if key in name for issue in issues]

    status = "warning" if matches else "ok"
    summary = (
        f"{len(matches)} known issue(s) curated for dataset '{name}'" if matches
        else f"no curated known issues for dataset '{name}'"
    )
    return {"check": "known_issue_lookup", "status": status, "summary": summary, "details": {"matches": matches}}
