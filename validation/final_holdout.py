#!/usr/bin/env python3
"""Final synthetic hold-out, written before and run once after the method freeze.

A generator family that shares no generator with fixtures.py or
heldout_validation.py, so no earlier result could have shaped it, and it is
run exactly once, after the implementation was tagged paper-method-freeze.
Whatever it reports is the result; a fix prompted by it would turn it into
development data.

How it differs from the earlier families:
- four classes (normal, scan, dos, exfil), under two class-prior regimes:
  skewed (0.80/0.12/0.06/0.02) and even (0.25 each);
- flow-like features (log-normal byte counts, Poisson packet counts,
  exponential durations, a categorical service) with a real but moderate
  class signal, instead of standard-normal noise with noise labels;
- 7,000 rows per frame; seeds 900-904 (per-check part) and 910-919 (suite);
- each defect is injected by a different mechanism than before (per-class
  host pools, flow fingerprints, class time windows, block-sorted rows).

Part 1: for each of the same 14 checks, 5 seeds x 2 regimes x {weak, strong,
no defect}. Part 2: the full applicable suite (22 checks via run_audit) on
30 clean flow-like corpora (10 seeds x 3 regimes: even, skewed, rare with a
1% class), every row its own flow, hosts and ports drawn from Zipf-weighted
pools large enough that no identifier is low-cardinality by construction.

Usage: venv/bin/python3 validation/final_holdout.py
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
from heldout_validation import CLEAN_APPLICABLE, full_cfg, small_cfg  # noqa: E402
from run_validation import CHECK_FUNCS  # noqa: E402

from ids2eval.audit import run_audit  # noqa: E402
from ids2eval.config import DEFAULTS  # noqa: E402
from ids2eval.data import dataset  # noqa: E402

N = 7000
CLASSES = np.array(["normal", "scan", "dos", "exfil"])
REGIMES = {"skewed": [0.80, 0.12, 0.06, 0.02], "even": [0.25, 0.25, 0.25, 0.25]}
SUITE_REGIMES = {**REGIMES, "rare": [0.70, 0.19, 0.10, 0.01]}
STRENGTHS = ("weak", "strong")
PART1_SEEDS = range(900, 905)
PART2_SEEDS = range(910, 920)
GROUP = ["src_ip", "src_port", "dst_ip", "dst_port", "proto"]
OUT = Path(__file__).resolve().parent.parent / "results" / "analysis" / "final_holdout.json"
FEATS = ["bytes_out", "bytes_in", "pkts_out", "pkts_in", "duration", "mean_iat"]
# per-class multiplicative shifts: moderate signal, no single feature separates a class
SHIFT = {"normal": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0], "scan": [0.6, 0.7, 0.8, 0.7, 0.7, 1.2],
         "dos": [1.5, 0.8, 1.4, 0.9, 0.8, 0.7], "exfil": [1.4, 1.2, 1.1, 1.2, 1.3, 1.1]}


def labels(rng, n, p):
    return rng.choice(CLASSES, size=n, p=p)


def flow_features(rng, y):
    n = len(y)
    shift = np.array([SHIFT[c] for c in y])
    out = pd.DataFrame({
        "bytes_out": rng.lognormal(7.0, 1.2, n) * shift[:, 0],
        "bytes_in": rng.lognormal(7.5, 1.3, n) * shift[:, 1],
        "pkts_out": rng.poisson(12 * shift[:, 2]) + 1.0,
        "pkts_in": rng.poisson(14 * shift[:, 3]) + 1.0,
        "duration": rng.exponential(2.0 * shift[:, 4]),
        "mean_iat": rng.exponential(0.2 * shift[:, 5]),
    })
    out["service"] = rng.choice(["http", "dns", "ssh", "smtp", "ntp", "tls"], n)
    return out


def frame(rng, p, n=N):
    y = labels(rng, n, p)
    df = flow_features(rng, y)
    df["label"] = y
    return df


def zipf_pick(rng, pool, n, a=1.3):
    w = 1.0 / np.arange(1, len(pool) + 1) ** a
    return rng.choice(pool, size=n, p=w / w.sum())


def class_tied(rng, y, pools, agreement, shared):
    """Values from a per-class pool with probability `agreement`, else from a shared pool."""
    own = np.array([rng.choice(pools[c]) for c in y])
    other = rng.choice(shared, len(y))
    return np.where(rng.random(len(y)) < agreement, own, other)


def host_pools(rng, base):
    return {c: [f"{base}.{i}.{j}" for j in rng.integers(1, 250, 3)] for i, c in enumerate(CLASSES)}


# --- generators: (rng, priors, strength) -> (train, test, cfg); strength None = no defect ---

def g_dedup(rng, p, s):
    tr, te = frame(rng, p), frame(rng, p)
    if s:
        k = int(N * {"weak": 0.01, "strong": 0.15}[s])
        idx = rng.integers(0, N, k)
        te.iloc[:k] = tr.iloc[idx].to_numpy()
    return tr, te, small_cfg()


def g_label_conflict(rng, p, s):
    tr, te = frame(rng, p), frame(rng, p)
    if s:
        k = int(N * {"weak": 0.005, "strong": 0.05}[s])
        dup = tr.sample(n=k, random_state=int(rng.integers(1e6))).copy()
        dup["label"] = [rng.choice(CLASSES[CLASSES != c]) for c in dup["label"]]
        tr = pd.concat([tr, dup], ignore_index=True)
    return tr, te, small_cfg()


def g_near_dup(rng, p, s):
    tr = frame(rng, p)
    if s:
        frac = {"weak": 0.03, "strong": 0.4}[s]
        src = tr.index[tr["label"] == "normal"]
        tgt = tr.index[tr["label"] != "normal"]
        k = int(len(tgt) * frac)
        chosen, donors = tgt[:k], rng.choice(src, k)
        tr.loc[chosen, FEATS] = tr.loc[donors, FEATS].to_numpy() * (1 + rng.normal(scale=1e-10, size=(k, 6)))
        tr.loc[chosen, "service"] = tr.loc[donors, "service"].to_numpy()
    return tr, tr.copy(), small_cfg()


def g_identity(rng, p, s):
    tr, te = frame(rng, p), frame(rng, p)
    pools = host_pools(rng, "10.20")
    shared = [f"10.30.{a}.{b}" for a, b in rng.integers(0, 250, (500, 2))]
    for df in (tr, te):
        if s:
            df["src_ip"] = class_tied(rng, df["label"], pools, {"weak": 0.8, "strong": 1.0}[s], shared)
        else:
            df["src_ip"] = zipf_pick(rng, shared, len(df))
    return tr, te, small_cfg(id_like_columns=["src_ip"])


def g_low_card(rng, p, s):
    tr = frame(rng, p)
    k = {"weak": 45, "strong": 8}[s] if s else 3000
    pool = [f"172.20.{a}.{b}" for a, b in rng.integers(0, 250, (k, 2))]
    tr["src_ip"] = zipf_pick(rng, pool, N, a=0.8)
    return tr, None, small_cfg(id_like_columns=["src_ip"])


def g_port_proto(rng, p, s):
    tr, te = frame(rng, p), frame(rng, p)
    port_of = {"normal": 443, "scan": 22, "dos": 80, "exfil": 8443}
    proto_of = {"normal": "tcp", "scan": "tcp", "dos": "udp", "exfil": "udp"}
    common = np.array([20, 21, 22, 25, 53, 80, 110, 123, 143, 443, 993, 3389, 8080, 8443])
    for df in (tr, te):
        if s:
            keep = rng.random(len(df)) < {"weak": 0.85, "strong": 1.0}[s]
            df["dst_port"] = np.where(keep, df["label"].map(port_of), rng.choice(common, len(df)))
            df["proto"] = np.where(keep, df["label"].map(proto_of), rng.choice(["tcp", "udp"], len(df)))
        else:
            df["dst_port"] = rng.choice(common, len(df))
            df["proto"] = rng.choice(["tcp", "udp"], len(df))
    return tr, te, small_cfg(id_like_columns=["dst_port"])


def g_one_rule(rng, p, s):
    tr, te = frame(rng, p), frame(rng, p)
    if s:
        edges = np.cumsum(p)[:-1]
        for df in (tr, te):
            q = df["duration"].rank(pct=True).to_numpy()
            y = CLASSES[np.searchsorted(edges, q)]
            flip = rng.random(len(df)) < {"weak": 0.03, "strong": 0.0}[s]
            df["label"] = np.where(flip, labels(rng, len(df), p), y)
    return tr, te, small_cfg()


def g_row_order(rng, p, s):
    tr = frame(rng, p)
    if s:
        k = int(N * {"weak": 0.7, "strong": 1.0}[s])
        block = tr.iloc[:k].sort_values("label", kind="stable")
        tr = pd.concat([block, tr.iloc[k:]], ignore_index=True)
    return tr, tr.copy(), small_cfg()


def ts(seconds):
    return pd.Series(pd.Timestamp("2026-05-04") + pd.to_timedelta(seconds, unit="s")).astype(str)


def g_temporal_leak(rng, p, s):
    tr, te = frame(rng, p), frame(rng, p)
    day = 86400.0
    for df in (tr, te):
        if s:
            width = {"weak": 0.55, "strong": 0.2}[s]
            start = {c: i * (1 - width) / 3 for i, c in enumerate(CLASSES)}
            frac = np.array([start[c] for c in df["label"]]) + rng.uniform(0, width, len(df))
        else:
            frac = rng.uniform(0, 1, len(df))
        df["ts"] = ts(frac * day)
    return tr, te, small_cfg(timestamp_column="ts")


def g_temporal_realism(rng, p, s):
    tr = frame(rng, p)
    t = rng.uniform(0, 86400, N)
    if s:
        width = {"weak": 60.0, "strong": 15.0}[s]
        attack = (tr["label"] != "normal").to_numpy()
        t[attack] = 43000 + rng.uniform(0, width, attack.sum())
    tr["ts"] = ts(t)
    return tr, None, small_cfg(timestamp_column="ts")


def g_homogeneity(rng, p, s):
    if s:
        tr, te = frame(rng, p), frame(rng, p)
        k = int(N * {"weak": 0.1, "strong": 0.25}[s])
        te.iloc[:k] = tr.iloc[rng.integers(0, N, k)].to_numpy()
        return tr, te, small_cfg()
    parts = []
    for c, share in zip(CLASSES, p, strict=True):
        n = max(int(2 * N * share), 60)
        templates = flow_features(rng, np.full(30, c))
        rows = templates.iloc[zipf_pick(rng, np.arange(30), n, a=1.0)].reset_index(drop=True)
        rows["label"] = c
        parts.append(rows)
    pop = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=int(rng.integers(1e6)))
    pop = pop.reset_index(drop=True)
    half = len(pop) // 2
    return pop.iloc[:half].reset_index(drop=True), pop.iloc[half:].reset_index(drop=True), small_cfg()


def flows(rng, n_flows, per_flow):
    fid = np.repeat(np.arange(n_flows), per_flow)
    return pd.DataFrame({"src_ip": [f"10.40.{f // 250}.{f % 250}" for f in fid], "src_port": 20000 + fid,
                         "dst_ip": "192.168.7.1", "dst_port": 443, "proto": "tcp", "_fid": fid})


def g_group_leak(rng, p, s):
    df = flows(rng, 700, 10)
    if s:
        spread = {"weak": 0.5, "strong": 0.15}[s]
        flow_class = labels(rng, 700, p)
        centre = np.log(flow_features(rng, np.full(700, "normal"))[FEATS].to_numpy() + 1)
        x = centre[df["_fid"]] * np.exp(rng.normal(scale=spread, size=(len(df), 6)))
        df[FEATS] = x
        df["label"] = flow_class[df["_fid"]]
    else:
        y = labels(rng, len(df), p)
        df = pd.concat([df, flow_features(rng, y)[FEATS]], axis=1)
        df["label"] = y
    return df.drop(columns="_fid"), None, full_cfg()


def g_robustness(rng, p, s):
    y = labels(rng, 2 * N, p)
    df = flow_features(rng, y)[FEATS]
    pools = host_pools(rng, "10.50")
    shared = [f"10.60.{a}.{b}" for a, b in rng.integers(0, 250, (2000, 2))]
    if s:
        df["label"] = labels(rng, 2 * N, p)  # features carry no signal; only the identifier does
        df["src_ip"] = class_tied(rng, df["label"], pools, {"weak": 0.85, "strong": 1.0}[s], shared)
    else:
        df["label"] = y
        df["src_ip"] = zipf_pick(rng, shared, 2 * N)
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
        for seed in PART1_SEEDS:
            for regime, p in REGIMES.items():
                for s in (*STRENGTHS, None):
                    rng = np.random.default_rng([seed, list(REGIMES).index(regime), 0 if s is None else
                                                 STRENGTHS.index(s) + 1])
                    tr, te, cfg = gen(rng, p, s)
                    status = CHECK_FUNCS[check](tr, te, cfg)["status"]
                    rows.append({"seed": seed, "regime": regime, "strength": s or "negative", "status": status})
        summ = {k: {"n": sum(r["strength"] == k for r in rows),
                    "fired": sum(r["strength"] == k and r["status"] != "ok" for r in rows)}
                for k in (*STRENGTHS, "negative")}
        out[check] = {"summary": summ, "runs": rows}
        print(check, summ, flush=True)
    return out


def clean_corpus(rng, p, n=N):
    y = labels(rng, n, p)
    df = flow_features(rng, y)
    df["label"] = y
    hosts = [f"10.{a}.{b}.{c}" for a, b, c in rng.integers(0, 250, (4000, 3))]
    servers = [f"172.16.{a}.{b}" for a, b in rng.integers(0, 250, (800, 2))]
    ports = rng.choice(np.arange(1, 49152), 300, replace=False)
    df["src_ip"] = zipf_pick(rng, hosts, n, a=0.9)
    df["dst_ip"] = zipf_pick(rng, servers, n, a=0.9)
    df["src_port"] = rng.permutation(np.arange(49152, 49152 + n))  # every row its own flow
    df["dst_port"] = zipf_pick(rng, ports, n, a=0.9)
    df["proto"] = rng.choice(["tcp", "udp"], n, p=[0.7, 0.3])
    df["ts"] = ts(np.sort(rng.uniform(0, 86400, n)))
    return df.sample(frac=1.0, random_state=int(rng.integers(1e6))).reset_index(drop=True)


def part2() -> dict:
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for regime, p in SUITE_REGIMES.items():
            for seed in PART2_SEEDS:
                df = clean_corpus(np.random.default_rng([seed, list(SUITE_REGIMES).index(regime)]), p)
                path = Path(tmp) / f"clean_{regime}_{seed}.csv"
                df.to_csv(path, index=False)
                cfg = copy.deepcopy(DEFAULTS)
                cfg["dataset"].update({"name": f"final-clean-{regime}-{seed}", "raw_files": [str(path)],
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
                summaries = {f["check"]: f["summary"] for f in findings if f["status"] != "ok"}
                runs.append({"regime": regime, "seed": seed, "statuses": statuses, "non_ok_summaries": summaries})
                print(regime, seed, "flags:", [c for c, st in statuses.items() if st == "flag"],
                      "warnings:", [c for c, st in statuses.items() if st == "warning"], flush=True)
    per_check = {c: {"flag": sum(r["statuses"].get(c) == "flag" for r in runs),
                     "warning": sum(r["statuses"].get(c) == "warning" for r in runs)} for c in CLEAN_APPLICABLE}
    return {"n_datasets": len(runs),
            "datasets_with_any_flag": sum(any(st == "flag" for st in r["statuses"].values()) for r in runs),
            "datasets_with_any_warning": sum(any(st == "warning" for st in r["statuses"].values()) for r in runs),
            "per_check": per_check, "runs": runs}


def main() -> None:
    if OUT.exists():
        sys.exit(f"{OUT} exists: the final hold-out is run once; remove it only if that run was invalid")
    results = {"part1": part1()}
    results["part2"] = part2()
    OUT.write_text(json.dumps(results, indent=2))
    p2 = results["part2"]
    print(f"clean corpora with any flag: {p2['datasets_with_any_flag']}/{p2['n_datasets']}, "
          f"with any warning: {p2['datasets_with_any_warning']}/{p2['n_datasets']}")
    print("DONE")


if __name__ == "__main__":
    main()
