"""Flow-identity leakage check: same flow tuple on both sides of the split.

Direct counterpart to resplit_falsification, which asks "would a
session-grouped split cost accuracy" without ever naming which specific
rows would move. This check names them: given schema.flow_id_columns
(typically a 5-tuple, e.g. source/destination IP, source/destination
port, protocol, or whatever subset survives in a given release), it
finds identity values that appear in both train and test. Many NIDS
papers still split flow-level data at random rather than by session,
letting the same connection contribute a row to both sides, so a model
can partly recognize the connection rather than the attack behavior.

Unlike label_conflict_check (which compares on every feature column),
this compares on only the columns named in schema.flow_id_columns, so
two different flows that happen to share a source IP and port (against
different destinations, say) are correctly treated as different
identities, not merged into one.

No-ops if schema.flow_id_columns is empty or none of its columns survive
in the loaded data (many public releases already strip IP columns before
distribution, e.g. the NetFlow-V2 mirrors this project audits).
"""

from __future__ import annotations

import pandas as pd


def check(train_df: pd.DataFrame, test_df: pd.DataFrame, cfg: dict) -> dict:
    flow_cols = [c for c in cfg["schema"]["flow_id_columns"] if c in train_df.columns]
    if not flow_cols:
        return {
            "check": "flow_group_leakage_check", "status": "ok",
            "summary": "no schema.flow_id_columns configured", "details": {},
        }

    train_keys = pd.util.hash_pandas_object(train_df[flow_cols], index=False)
    test_keys = pd.util.hash_pandas_object(test_df[flow_cols], index=False)
    overlap = set(train_keys.to_numpy()) & set(test_keys.to_numpy())

    if not overlap:
        return {
            "check": "flow_group_leakage_check", "status": "ok",
            "summary": f"no flow identity in {flow_cols} appears on both sides of the split",
            "details": {"flow_id_columns": flow_cols},
        }

    train_rows = int(train_keys.isin(overlap).sum())
    test_rows = int(test_keys.isin(overlap).sum())
    summary = (
        f"{len(overlap):,} flow identit{'y' if len(overlap) == 1 else 'ies'} in {flow_cols} "
        f"appear on both sides of the split, touching {train_rows:,} train row(s) and "
        f"{test_rows:,} test row(s); a model can partly recognize the connection instead "
        f"of the attack behavior on these rows"
    )
    return {
        "check": "flow_group_leakage_check", "status": "flag", "summary": summary,
        "details": {
            "flow_id_columns": flow_cols,
            "overlapping_identities": len(overlap),
            "train_rows_affected": train_rows,
            "test_rows_affected": test_rows,
        },
    }
