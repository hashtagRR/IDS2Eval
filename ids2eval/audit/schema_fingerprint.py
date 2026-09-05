"""Known-extractor-bug warning via column-name schema fingerprinting.

Not a per-dataset curated issue list (that's the v2 known_issue_lookup
check) — this matches the *extractor tool*'s column-naming signature
(e.g. CICFlowMeter) and surfaces that tool's documented bugs generally,
regardless of which specific dataset the columns came from.

Extend KNOWN_EXTRACTORS as more extractor signatures get curated.
"""

from __future__ import annotations

import pandas as pd

KNOWN_EXTRACTORS = {
    "CICFlowMeter": {
        # A handful of column names distinctive enough to fingerprint the
        # tool without requiring every one of its ~80 columns present.
        "signature_columns": {
            "Flow Duration", "Fwd Packet Length Mean", "Bwd Packet Length Mean",
            "Flow Bytes/s", "Flow Packets/s", "Fwd IAT Mean", "Bwd IAT Mean",
            "Init_Win_bytes_forward", "Init_Win_bytes_backward",
        },
        "match_threshold": 0.6,
        "warning": (
            "CICFlowMeter is known to have miscalculated ~34 features in early "
            "releases (Rosay et al. 2021), motivating the corrected LYCOS-IDS2017 "
            "release. Verify which extractor version produced this data before "
            "trusting derived-rate/duration features."
        ),
    },
}


def check(train_df: pd.DataFrame, cfg: dict) -> dict:
    columns = set(train_df.columns)
    matches = {}
    for name, spec in KNOWN_EXTRACTORS.items():
        overlap = spec["signature_columns"] & columns
        match_share = len(overlap) / len(spec["signature_columns"])
        if match_share >= spec["match_threshold"]:
            matches[name] = {"match_share": match_share, "warning": spec["warning"]}

    status = "warning" if matches else "ok"
    summary = (
        f"matched extractor signature(s): {list(matches)}" if matches
        else "no known extractor signature matched"
    )
    return {
        "check": "schema_fingerprint_check", "status": status, "summary": summary,
        "details": matches,
    }
