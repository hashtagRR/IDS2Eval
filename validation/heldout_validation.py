#!/usr/bin/env python3
"""Held-out validation of IDS2Eval's checks, written after the implementation
was frozen (so unlike fixtures.py it could not have shaped the code).

Part 1, per-check discrimination: new positive and negative fixture
generators for the 14 checks in fixtures.py, varied over 5 seeds, two defect
strengths (weak, strong) and two class balances (50/50, 90/10). Reports, per
check, the share of positive fixtures that fire and of negative fixtures
that fire.

Part 2, suite-level false flags: the full applicable audit (run_audit, 22
checks) on 30 defect-free datasets that look like flow records (identifier,
port, protocol, timestamp and 5-tuple columns, every row its own flow),
over three class balances. Reports per-check flag and warning rates and the
share of clean datasets with at least one flag.

Usage: venv/bin/python3 validation/heldout_validation.py
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from run_validation import CHECK_FUNCS  # noqa: E402

from ids2eval.audit import run_audit  # noqa: E402
from ids2eval.config import DEFAULTS  # noqa: E402
from ids2eval.data import dataset  # noqa: E402

N = 4000
SEEDS = range(100, 105)  # disjoint from fixtures.py's seeds
BALANCES = {"balanced": 0.5, "imbalanced": 0.1}
STRENGTHS = ("weak", "strong")
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "heldout_validation.json"
GROUP = ["src_ip", "src_port", "dst_ip", "dst_port", "proto"]


def small_cfg(**schema) -> dict:
    base = {"label_column": "label", "attack_category_column": None, "drop_columns": [], "id_like_columns": [],
            "timestamp_column": None, "flow_id_columns": [], "scenario_column": None, "feature_categories": {}}
    base.update(schema)
    return {"random_seed": 0, "schema": base, "dataset": {"group_columns": []},
            "audit": {"materiality_thresholds": {}}}


def full_cfg(**over) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    cfg["schema"]["label_column"] = "label"
    cfg["dataset"]["raw_files"] = ["<in-memory>"]
    cfg["dataset"]["group_columns"] = list(GROUP)
    cfg["schema"]["drop_columns"] = list(GROUP)
    cfg["audit"]["repeated_seed_count"] = 5
    for key, value in over.items():
        section, field = key.split("__")
        cfg[section][field] = value
    return cfg


def noise(rng, n, k=6):
    return pd.DataFrame(rng.normal(size=(n, k)), columns=[f"f{i}" for i in range(k)])


def labels(rng, n, m):
    return rng.choice(["benign", "attack"], size=n, p=[1 - m, m])


def ts(offsets):
    return pd.Series(pd.Timestamp("2026-03-01") + pd.to_timedelta(offsets, unit="s")).astype(str)


def noisy_copy(rng, y, agreement):
    """A column that equals a label-derived code with probability `agreement`."""
    code = np.where(y == "benign", "A", "B")
    flip = rng.random(len(y)) > agreement
    return np.where(flip, np.where(code == "A", "B", "A"), code)


def pair(rng, m):
    tr = noise(rng, N)
    tr["label"] = labels(rng, N, m)
    te = noise(rng, N)
    te["label"] = labels(rng, N, m)
    return tr, te


# --- generators: (rng, m, strength) -> (train, test, cfg); strength None = negative ---

def g_dedup(rng, m, s):
    tr, te = pair(rng, m)
    if s:
        k = int(N * {"weak": 0.02, "strong": 0.2}[s])
        te.iloc[:k] = tr.iloc[:k].to_numpy()
    return tr, te, small_cfg()


def g_label_conflict(rng, m, s):
    tr, te = pair(rng, m)
    if s:
        k = int(N * {"weak": 0.01, "strong": 0.1}[s])
        dup = tr.iloc[:k].copy()
        dup["label"] = dup["label"].map({"benign": "attack", "attack": "benign"})
        tr = pd.concat([tr, dup], ignore_index=True)
    return tr, te, small_cfg()


def g_near_dup(rng, m, s):
    a = noise(rng, N // 2)
    a["label"] = "benign"
    if s:
        k = int(N // 2 * {"weak": 0.05, "strong": 0.5}[s])
        b = pd.concat([a.iloc[:k, :-1] + rng.normal(scale=1e-8, size=(k, 6)), noise(rng, N // 2 - k) + 8.0],
                      ignore_index=True)
    else:
        b = noise(rng, N // 2) + 8.0
    b["label"] = "attack"
    tr = pd.concat([a, b], ignore_index=True)
    return tr, tr.copy(), small_cfg()


def g_identity(rng, m, s):
    tr, te = pair(rng, m)
    for df in (tr, te):
        if s:
            df["src_ip"] = noisy_copy(rng, df["label"].to_numpy(), {"weak": 0.9, "strong": 1.0}[s])
        else:
            df["src_ip"] = rng.integers(0, N, len(df)).astype(str)
    return tr, te, small_cfg(id_like_columns=["src_ip"])


def g_low_card(rng, m, s):
    tr, _ = pair(rng, m)
    k = {"weak": 40, "strong": 5}[s] if s else N
    tr["src_ip"] = rng.integers(0, k, N).astype(str)
    return tr, None, small_cfg(id_like_columns=["src_ip"])


def g_port_proto(rng, m, s):
    tr, te = pair(rng, m)
    for df in (tr, te):
        if s:
            code = noisy_copy(rng, df["label"].to_numpy(), {"weak": 0.9, "strong": 1.0}[s])
            df["dst_port"] = np.where(code == "A", 443, 4444)
            df["proto"] = np.where(code == "A", "tcp", "udp")
        else:
            df["dst_port"] = rng.choice([22, 53, 80, 443, 4444], len(df))
            df["proto"] = rng.choice(["tcp", "udp"], len(df))
    return tr, te, small_cfg(id_like_columns=["dst_port"])


def g_one_rule(rng, m, s):
    tr, te = pair(rng, m)
    if s:
        for df in (tr, te):
            cut = np.quantile(df["f0"], 1 - m)
            y = np.where(df["f0"] > cut, "attack", "benign")
            flip = rng.random(len(df)) < {"weak": 0.02, "strong": 0.0}[s]
            df["label"] = np.where(flip, np.where(y == "attack", "benign", "attack"), y)
    return tr, te, small_cfg()


def g_row_order(rng, m, s):
    tr, _ = pair(rng, m)
    if s:
        k = int(N * {"weak": 0.8, "strong": 1.0}[s])
        head = tr.iloc[:k].sort_values("label", kind="stable")
        tr = pd.concat([head, tr.iloc[k:]], ignore_index=True)
    return tr, tr.copy(), small_cfg()


def g_temporal_leak(rng, m, s):
    tr, te = pair(rng, m)
    for df in (tr, te):
        y = df["label"].to_numpy()
        if s:
            lo, hi = {"weak": (300, 700), "strong": (900, 0)}[s]
            off = np.where(y == "benign", rng.uniform(0, hi or 100, len(df)), rng.uniform(lo, 1000, len(df)))
        else:
            off = rng.uniform(0, 1000, len(df))
        df["ts"] = ts(off)
    return tr, te, small_cfg(timestamp_column="ts")


def g_temporal_realism(rng, m, s):
    tr, _ = pair(rng, m)
    y = tr["label"].to_numpy()
    if s:
        w = {"weak": 30, "strong": 10}[s]
        off = np.where(y == "benign", rng.uniform(0, 1000, N), rng.uniform(500, 500 + w, N))
    else:
        off = rng.uniform(0, 1000, N)
    tr["ts"] = ts(off)
    return tr, None, small_cfg(timestamp_column="ts")


def g_homogeneity(rng, m, s):
    if s:
        tr, te = pair(rng, m)
        k = int(N * {"weak": 0.15, "strong": 0.3}[s])
        te.iloc[:k] = tr.iloc[:k].to_numpy()
        return tr, te, small_cfg()
    parts = []
    for cls, share in (("benign", 1 - m), ("attack", m)):
        n = int(2 * N * share)
        templates = noise(rng, 50)
        rows = templates.iloc[rng.integers(0, 50, n)].reset_index(drop=True)
        rows["label"] = cls
        parts.append(rows)
    pop = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=int(rng.integers(1e6))) \
        .reset_index(drop=True)
    half = len(pop) // 2
    return pop.iloc[:half].reset_index(drop=True), pop.iloc[half:].reset_index(drop=True), small_cfg()


def flows(n_groups, per):
    gid = np.repeat(np.arange(n_groups), per)
    return pd.DataFrame({"src_ip": [f"10.1.{g // 250}.{g % 250}" for g in gid], "src_port": 1024 + gid,
                         "dst_ip": "192.168.0.1", "dst_port": 443, "proto": "tcp", "_gid": gid})


def g_group_leak(rng, m, s):
    df = flows(400, 10)
    if s:
        scale, spread = {"weak": (1.0, 0.6), "strong": (3.0, 0.3)}[s]
        centroids = rng.normal(scale=scale, size=(400, 6))
        df[[f"f{i}" for i in range(6)]] = centroids[df["_gid"]] + rng.normal(scale=spread, size=(len(df), 6))
        df["label"] = rng.choice(["benign", "attack"], 400, p=[1 - m, m])[df["_gid"]]
    else:
        df[[f"f{i}" for i in range(6)]] = rng.normal(size=(len(df), 6))
        cut = np.quantile(df["f0"], 1 - m)
        df["label"] = np.where(df["f0"] > cut, "attack", "benign")
    return df.drop(columns="_gid"), None, full_cfg()


def g_robustness(rng, m, s):
    df = noise(rng, 2 * N)
    df["label"] = labels(rng, 2 * N, m)
    if s:
        df["src_ip"] = noisy_copy(rng, df["label"].to_numpy(), {"weak": 0.9, "strong": 1.0}[s])
    else:
        cut = np.quantile(df["f0"], 1 - m)
        df["label"] = np.where(df["f0"] > cut, "attack", "benign")
        df["src_ip"] = rng.integers(0, 2 * N, 2 * N).astype(str)
    return df, None, full_cfg(dataset__group_columns=[], schema__drop_columns=[], schema__id_like_columns=["src_ip"])


GENERATORS = {
    "dedup_check": g_dedup, "label_conflict_check": g_label_conflict, "near_duplicate_class_check": g_near_dup,
    "identity_column_flag": g_identity, "low_cardinality_warning": g_low_card,
    "port_protocol_shortcut_check": g_port_proto, "one_rule_check": g_one_rule,
    "row_order_leakage_check": g_row_order, "temporal_leakage_check": g_temporal_leak,
    "temporal_realism_check": g_temporal_realism, "homogeneity_test": g_homogeneity,
    "resplit_falsification": g_group_leak, "repeated_seed_falsification_check": g_group_leak,
    "result_robustness_check": g_robustness,
}


def part1() -> dict:
    out = {}
    for check, gen in GENERATORS.items():
        rows = []
        for seed in SEEDS:
            for bal, m in BALANCES.items():
                for s in (*STRENGTHS, None):
                    rng = np.random.default_rng(seed * 1000 + int(m * 100) + (0 if s is None else STRENGTHS.index(s) + 1))
                    tr, te, cfg = gen(rng, m, s)
                    status = CHECK_FUNCS[check](tr, te, cfg)["status"]
                    rows.append({"seed": seed, "balance": bal, "strength": s or "negative", "status": status})
        summ = {}
        for key in (*STRENGTHS, "negative"):
            sel = [r for r in rows if r["strength"] == key]
            summ[key] = {"n": len(sel), "fired": sum(r["status"] != "ok" for r in sel)}
        out[check] = {"summary": summ, "runs": rows}
        print(check, summ, flush=True)
    return out


CLEAN_APPLICABLE = [
    "dedup_check", "label_conflict_check", "near_duplicate_class_check", "leakage_screen", "one_rule_check",
    "feature_auc_ranking_check", "identity_column_flag", "port_protocol_shortcut_check", "temporal_leakage_check",
    "temporal_realism_check", "flow_group_leakage_check", "row_order_leakage_check", "homogeneity_test",
    "resplit_falsification", "class_distribution_report", "low_cardinality_warning", "schema_fingerprint_check",
    "data_integrity_check", "artifact_sensitivity_check", "result_robustness_check", "seed_sensitivity_check",
    "repeated_seed_falsification_check",
]


def clean_dataset(rng, m, n=6000):
    df = noise(rng, n)
    df["label"] = labels(rng, n, m)
    df["src_ip"] = [f"10.{a}.{b}.{c}" for a, b, c in rng.integers(0, 255, (n, 3))]
    df["dst_ip"] = [f"172.16.{a}.{b}" for a, b in rng.integers(0, 255, (n, 2))]
    df["src_port"] = rng.integers(1024, 65535, n)
    df["dst_port"] = rng.choice([22, 53, 80, 123, 443, 8080], n)
    df["proto"] = rng.choice(["tcp", "udp"], n)
    df["ts"] = ts(rng.uniform(0, 86400, n))
    return df


def part2(seeds=range(200, 210)) -> dict:
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for bal, m in {"balanced": 0.5, "imbalanced_10pct": 0.1, "imbalanced_2pct": 0.02}.items():
            for seed in seeds:
                rng = np.random.default_rng(seed)
                df = clean_dataset(rng, m)
                path = Path(tmp) / f"clean_{bal}_{seed}.csv"
                df.to_csv(path, index=False)
                cfg = copy.deepcopy(DEFAULTS)
                cfg["dataset"].update({"name": f"clean-{bal}-{seed}", "raw_files": [str(path)],
                                       "group_columns": list(GROUP)})
                cfg["schema"].update({"label_column": "label", "drop_columns": ["ts"],
                                      "id_like_columns": ["src_ip", "dst_ip", "src_port", "dst_port"],
                                      "flow_id_columns": list(GROUP), "timestamp_column": "ts"})
                for name in CLEAN_APPLICABLE:
                    cfg["audit"][name] = True
                for name in set(cfg["audit"]) - set(CLEAN_APPLICABLE):
                    if isinstance(cfg["audit"][name], bool):
                        cfg["audit"][name] = False
                cfg["audit"]["repeated_seed_count"] = 5
                combined = dataset.load_raw_combined(cfg["dataset"], seed=0)
                train, test = dataset._random_split(combined, "label", cfg["dataset"], seed=0)
                findings = run_audit(train, test, cfg)
                statuses = {f["check"]: f["status"] for f in findings}
                runs.append({"balance": bal, "seed": seed, "statuses": statuses})
                flagged = [c for c, st in statuses.items() if st == "flag"]
                print(bal, seed, "flags:", flagged, "warnings:", [c for c, st in statuses.items() if st == "warning"],
                      flush=True)
    per_check = {c: {"flag": sum(r["statuses"].get(c) == "flag" for r in runs),
                     "warning": sum(r["statuses"].get(c) == "warning" for r in runs)} for c in CLEAN_APPLICABLE}
    any_flag = sum(any(st == "flag" for st in r["statuses"].values()) for r in runs)
    return {"n_datasets": len(runs), "datasets_with_any_flag": any_flag, "per_check": per_check, "runs": runs}


def main() -> None:
    results = {"part1": part1()}
    OUT.write_text(json.dumps(results, indent=2))
    results["part2"] = part2()
    OUT.write_text(json.dumps(results, indent=2))
    p2 = results["part2"]
    print(f"clean datasets with any flag: {p2['datasets_with_any_flag']}/{p2['n_datasets']}")
    print("DONE")


if __name__ == "__main__":
    main()
