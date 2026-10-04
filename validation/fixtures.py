"""Synthetic validation corpus for IDS2Eval's own checks.

Each defect gets a POSITIVE fixture (defect deliberately injected) and a
NEGATIVE fixture (defect deliberately absent, otherwise matched as closely
as possible), and the relevant check is run against both. A check that
behaves correctly should fire (flag/warning) on the positive fixture and
stay clean (ok) on the matched negative one. This validates the checks
themselves against known ground truth, rather than only running them
against real datasets whose true defect status is itself the thing being
investigated.

Every fixture is small (a few thousand rows) and fully synthetic - no real
dataset involved - built with a fixed numpy RandomState per fixture so the
corpus is reproducible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N = 4000  # rows per split, small enough to run in seconds


def base_cfg(**schema_overrides) -> dict:
    schema = {
        "label_column": "label",
        "attack_category_column": None,
        "drop_columns": [],
        "id_like_columns": [],
        "timestamp_column": None,
        "flow_id_columns": [],
        "scenario_column": None,
        "feature_categories": {},
    }
    schema.update(schema_overrides)
    return {
        "random_seed": 0,
        "schema": schema,
        "dataset": {"group_columns": []},
        "audit": {"materiality_thresholds": {}},
    }


def _noise_features(rng: np.random.RandomState, n: int, k: int = 6) -> pd.DataFrame:
    return pd.DataFrame(rng.normal(size=(n, k)), columns=[f"f{i}" for i in range(k)])


def _labels(rng: np.random.RandomState, n: int, classes=("benign", "attack")) -> np.ndarray:
    return rng.choice(classes, size=n)


# --- 1. Train/test exact duplication -> dedup_check -----------------------

def dedup_positive():
    rng = np.random.RandomState(1)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    # Overwrite a chunk of test with exact copies of train rows (features+label).
    k = N // 5
    test.iloc[:k] = train.iloc[:k].to_numpy()
    return train, test, base_cfg()


def dedup_negative():
    rng = np.random.RandomState(2)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    return train, test, base_cfg()


# --- 2. Label conflict (same features, different label) -> label_conflict_check

def label_conflict_positive():
    rng = np.random.RandomState(3)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    # Duplicate a chunk of rows but flip their label.
    k = N // 10
    dup = train.iloc[:k].copy()
    dup["label"] = dup["label"].map({"benign": "attack", "attack": "benign"})
    train = pd.concat([train, dup], ignore_index=True)
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    return train, test, base_cfg()


def label_conflict_negative():
    rng = np.random.RandomState(4)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    return train, test, base_cfg()


# --- 3. Near-duplicate class populations -> near_duplicate_class_check ----

def near_duplicate_class_positive():
    rng = np.random.RandomState(5)
    half = N // 2
    shared_core = _noise_features(rng, half)
    cls_a = shared_core.copy()
    cls_a["label"] = "benign"
    cls_b = shared_core.copy()
    cls_b["label"] = "attack"
    cls_b.iloc[:, :-1] += rng.normal(scale=1e-8, size=(half, 6))  # near-zero jitter
    train = pd.concat([cls_a, cls_b], ignore_index=True)
    test = train.copy()
    return train, test, base_cfg()


def near_duplicate_class_negative():
    rng = np.random.RandomState(6)
    half = N // 2
    cls_a = _noise_features(rng, half)
    cls_a["label"] = "benign"
    cls_b = _noise_features(rng, half) + 8.0  # well-separated cluster
    cls_b["label"] = "attack"
    train = pd.concat([cls_a, cls_b], ignore_index=True)
    test = train.copy()
    return train, test, base_cfg()


# --- 4. Identity-column leakage -> identity_column_flag --------------------

def identity_leak_positive():
    rng = np.random.RandomState(7)
    train = _noise_features(rng, N)
    labels = _labels(rng, N)
    train["label"] = labels
    train["src_ip"] = np.where(labels == "benign", "10.0.0.1", "10.0.0.2")
    test = _noise_features(rng, N)
    labels_t = _labels(rng, N)
    test["label"] = labels_t
    test["src_ip"] = np.where(labels_t == "benign", "10.0.0.1", "10.0.0.2")
    cfg = base_cfg(id_like_columns=["src_ip"])
    return train, test, cfg


def identity_leak_negative():
    rng = np.random.RandomState(8)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    train["src_ip"] = rng.randint(0, N, size=N).astype(str)  # unique per row, uncorrelated
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    test["src_ip"] = rng.randint(0, N, size=N).astype(str)
    cfg = base_cfg(id_like_columns=["src_ip"])
    return train, test, cfg


# --- 5. Low-cardinality identifier -> low_cardinality_warning --------------

def low_cardinality_positive():
    rng = np.random.RandomState(9)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    train["src_ip"] = rng.choice([f"10.0.0.{i}" for i in range(5)], size=N)  # 5 distinct values
    cfg = base_cfg(id_like_columns=["src_ip"])
    return train, None, cfg


def low_cardinality_negative():
    rng = np.random.RandomState(10)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    train["src_ip"] = rng.randint(0, N, size=N).astype(str)  # N distinct values
    cfg = base_cfg(id_like_columns=["src_ip"])
    return train, None, cfg


# --- 6. Port+protocol shortcut -> port_protocol_shortcut_check -------------

def port_protocol_positive():
    rng = np.random.RandomState(11)
    train = _noise_features(rng, N)
    labels = _labels(rng, N)
    train["label"] = labels
    train["dst_port"] = np.where(labels == "benign", 443, 31337)
    train["proto"] = np.where(labels == "benign", "tcp", "udp")
    test = _noise_features(rng, N)
    labels_t = _labels(rng, N)
    test["label"] = labels_t
    test["dst_port"] = np.where(labels_t == "benign", 443, 31337)
    test["proto"] = np.where(labels_t == "benign", "tcp", "udp")
    cfg = base_cfg(id_like_columns=["dst_port"])
    return train, test, cfg


def port_protocol_negative():
    rng = np.random.RandomState(12)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    train["dst_port"] = rng.choice([80, 443, 22, 53, 31337], size=N)
    train["proto"] = rng.choice(["tcp", "udp"], size=N)
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    test["dst_port"] = rng.choice([80, 443, 22, 53, 31337], size=N)
    test["proto"] = rng.choice(["tcp", "udp"], size=N)
    cfg = base_cfg(id_like_columns=["dst_port"])
    return train, test, cfg


# --- 7. One-rule shortcut -> one_rule_check ---------------------------------

def one_rule_positive():
    rng = np.random.RandomState(13)
    train = _noise_features(rng, N)
    train["label"] = np.where(train["f0"] > 0, "attack", "benign")  # f0 perfectly separates
    test = _noise_features(rng, N)
    test["label"] = np.where(test["f0"] > 0, "attack", "benign")
    return train, test, base_cfg()


def one_rule_negative():
    rng = np.random.RandomState(14)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)  # independent of every feature
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    return train, test, base_cfg()


# --- 8. Row-order leakage -> row_order_leakage_check ------------------------

def row_order_positive():
    rng = np.random.RandomState(15)
    train = _noise_features(rng, N)
    labels = np.array(["benign"] * (N // 2) + ["attack"] * (N - N // 2))  # blocked, not shuffled
    train["label"] = labels
    test = train.copy()
    return train, test, base_cfg()


def row_order_negative():
    rng = np.random.RandomState(16)
    train = _noise_features(rng, N)
    train["label"] = rng.permutation(_labels(rng, N))  # shuffled
    test = train.copy()
    return train, test, base_cfg()


# --- 9. Timestamp leakage -> temporal_leakage_check -------------------------

_EPOCH_BASE = pd.Timestamp("2026-01-01")  # a real datetime base, matching how an actual
# NIDS Timestamp column looks (e.g. CIC-IDS2018's own), not a raw numeric offset -
# pd.to_datetime's unit-auto-detection on a bare float/int Series is genuinely
# ambiguous (nanoseconds vs seconds since epoch), which this sidesteps entirely.


def _to_ts_strings(offsets_seconds: np.ndarray) -> pd.Series:
    return pd.Series(_EPOCH_BASE + pd.to_timedelta(offsets_seconds, unit="s")).astype(str)


def temporal_leak_positive():
    rng = np.random.RandomState(17)
    train = _noise_features(rng, N)
    labels = _labels(rng, N)
    train["label"] = labels
    # benign clustered early, attack clustered late in time
    train["ts"] = _to_ts_strings(np.where(
        labels == "benign", rng.uniform(0, 100, N), rng.uniform(900, 1000, N)
    ))
    test = _noise_features(rng, N)
    labels_t = _labels(rng, N)
    test["label"] = labels_t
    test["ts"] = _to_ts_strings(np.where(
        labels_t == "benign", rng.uniform(0, 100, N), rng.uniform(900, 1000, N)
    ))
    cfg = base_cfg(timestamp_column="ts")
    return train, test, cfg


def temporal_leak_negative():
    rng = np.random.RandomState(18)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    train["ts"] = _to_ts_strings(rng.uniform(0, 1000, N))  # uncorrelated with label
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    test["ts"] = _to_ts_strings(rng.uniform(0, 1000, N))
    cfg = base_cfg(timestamp_column="ts")
    return train, test, cfg


# --- 10. Temporal realism / narrow burst window -> temporal_realism_check --

def temporal_realism_positive():
    rng = np.random.RandomState(19)
    train = _noise_features(rng, N)
    labels = _labels(rng, N)
    train["label"] = labels
    # benign spread across full capture; attack confined to a narrow burst
    train["ts"] = _to_ts_strings(np.where(
        labels == "benign", rng.uniform(0, 1000, N), rng.uniform(500, 510, N)
    ))
    cfg = base_cfg(timestamp_column="ts")
    return train, None, cfg


def temporal_realism_negative():
    rng = np.random.RandomState(20)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    train["ts"] = _to_ts_strings(rng.uniform(0, 1000, N))  # both classes spread evenly
    cfg = base_cfg(timestamp_column="ts")
    return train, None, cfg


# --- 11. Cross-boundary copies vs inherent homogeneity -> homogeneity_test --

def homogeneity_positive():
    # Every population row is distinct, but a fifth of test is copied from train:
    # test rows match train far more often than train rows match each other.
    rng = np.random.RandomState(21)
    train = _noise_features(rng, N)
    train["label"] = _labels(rng, N)
    test = _noise_features(rng, N)
    test["label"] = _labels(rng, N)
    k = N // 5
    test.iloc[:k] = train.iloc[:k].to_numpy()
    return train, test, base_cfg()


def homogeneity_negative():
    # A mechanically repetitive population (50 distinct vectors per class, like
    # scripted attack traffic) split at random: rows match across the boundary
    # constantly, but no more often than within train itself.
    rng = np.random.RandomState(22)
    parts = []
    for cls in ("benign", "attack"):
        templates = _noise_features(rng, 50)
        rows = templates.iloc[rng.randint(0, 50, size=N)].reset_index(drop=True)
        rows["label"] = cls
        parts.append(rows)
    pop = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=0).reset_index(drop=True)
    return pop.iloc[:N].reset_index(drop=True), pop.iloc[N:].reset_index(drop=True), base_cfg()


# --- 12-13. Group-memorization leakage -> resplit / repeated-seed falsification
# These checks build their own splits from the combined raw data, so the
# fixture returns one combined frame (as `train`) plus a full default config.

GROUP_COLS = ["src_ip", "src_port", "dst_ip", "dst_port", "proto"]


def full_cfg(**overrides) -> dict:
    import copy

    from ids2eval.config import DEFAULTS
    cfg = copy.deepcopy(DEFAULTS)
    cfg["schema"]["label_column"] = "label"
    cfg["dataset"]["raw_files"] = ["<in-memory fixture>"]
    cfg["dataset"]["group_columns"] = list(GROUP_COLS)
    cfg["schema"]["drop_columns"] = list(GROUP_COLS)
    cfg["audit"]["repeated_seed_count"] = 5
    for key, value in overrides.items():
        section, field = key.split("__")
        cfg[section][field] = value
    return cfg


def _flows(rng: np.random.RandomState, n_groups: int, rows_per_group: int) -> pd.DataFrame:
    gid = np.repeat(np.arange(n_groups), rows_per_group)
    return pd.DataFrame({
        "src_ip": [f"10.0.{g // 250}.{g % 250}" for g in gid],
        "src_port": 1024 + gid,
        "dst_ip": "192.168.1.1",
        "dst_port": 443,
        "proto": "tcp",
        "_gid": gid,
    })


def group_leak_positive():
    # Each flow group has its own feature signature and its own random label,
    # unrelated to any feature that generalizes across groups: a random split
    # lets the model recognize groups it has already seen, a grouped split
    # cannot, so accuracy should collapse toward chance under grouping.
    rng = np.random.RandomState(23)
    n_groups, per = 400, 10
    df = _flows(rng, n_groups, per)
    centroids = rng.normal(scale=3.0, size=(n_groups, 6))
    feats = centroids[df["_gid"]] + rng.normal(scale=0.3, size=(len(df), 6))
    df[[f"f{i}" for i in range(6)]] = feats
    group_labels = rng.choice(["benign", "attack"], size=n_groups)
    df["label"] = group_labels[df["_gid"]]
    return df.drop(columns="_gid"), None, full_cfg()


def group_leak_negative():
    # Same flow-group structure, but the label depends on a per-row feature
    # that generalizes across groups, so grouping should not matter.
    rng = np.random.RandomState(24)
    df = _flows(rng, 400, 10)
    df[[f"f{i}" for i in range(6)]] = rng.normal(size=(len(df), 6))
    df["label"] = np.where(df["f0"] > 0, "attack", "benign")
    return df.drop(columns="_gid"), None, full_cfg()


# --- 14. Identity-column dependence -> result_robustness_check --------------

def robustness_positive():
    # The label is recoverable only from an identity column; dropping the
    # declared identity columns should collapse accuracy.
    rng = np.random.RandomState(25)
    df = _noise_features(rng, 2 * N)
    df["label"] = _labels(rng, 2 * N)
    df["src_ip"] = np.where(df["label"] == "benign", "10.0.0.1", "10.0.0.2")
    cfg = full_cfg(dataset__group_columns=[], schema__drop_columns=[], schema__id_like_columns=["src_ip"])
    return df, None, cfg


def robustness_negative():
    rng = np.random.RandomState(26)
    df = _noise_features(rng, 2 * N)
    df["label"] = np.where(df["f0"] > 0, "attack", "benign")
    df["src_ip"] = rng.randint(0, 2 * N, size=2 * N).astype(str)
    cfg = full_cfg(dataset__group_columns=[], schema__drop_columns=[], schema__id_like_columns=["src_ip"])
    return df, None, cfg


# --- Negative control: severe class imbalance, no leakage of any kind -------

def imbalance_control():
    # 0.5% minority class (under class_distribution_report's 1% rare-class rule),
    # labels independent of every feature, no duplicates,
    # no identity columns, rows shuffled. Only class_distribution_report should
    # react; every leakage-type check should stay clean.
    # 20,000 rows per split so the minority class (~100 rows) clears every
    # check's minimum class size and is actually tested, not skipped.
    rng = np.random.RandomState(27)
    n = 5 * N
    train = _noise_features(rng, n)
    train["label"] = rng.choice(["benign", "attack"], size=n, p=[0.995, 0.005])
    test = _noise_features(rng, n)
    test["label"] = rng.choice(["benign", "attack"], size=n, p=[0.995, 0.005])
    return train, test, base_cfg()


FIXTURES = {
    "dedup_check": {
        "defect": "exact train/test duplication",
        "positive": dedup_positive, "negative": dedup_negative,
    },
    "label_conflict_check": {
        "defect": "label conflict (identical features, different label)",
        "positive": label_conflict_positive, "negative": label_conflict_negative,
    },
    "near_duplicate_class_check": {
        "defect": "near-duplicate feature vectors across classes",
        "positive": near_duplicate_class_positive, "negative": near_duplicate_class_negative,
    },
    "identity_column_flag": {
        "defect": "identity column encodes the label",
        "positive": identity_leak_positive, "negative": identity_leak_negative,
    },
    "low_cardinality_warning": {
        "defect": "identity column has few distinct values",
        "positive": low_cardinality_positive, "negative": low_cardinality_negative,
    },
    "port_protocol_shortcut_check": {
        "defect": "port+protocol pair encodes the label",
        "positive": port_protocol_positive, "negative": port_protocol_negative,
    },
    "one_rule_check": {
        "defect": "single feature threshold perfectly separates classes",
        "positive": one_rule_positive, "negative": one_rule_negative,
    },
    "row_order_leakage_check": {
        "defect": "rows blocked by label instead of shuffled",
        "positive": row_order_positive, "negative": row_order_negative,
    },
    "temporal_leakage_check": {
        "defect": "timestamp alone encodes the label",
        "positive": temporal_leak_positive, "negative": temporal_leak_negative,
    },
    "temporal_realism_check": {
        "defect": "one class confined to a narrow time burst",
        "positive": temporal_realism_positive, "negative": temporal_realism_negative,
    },
    "homogeneity_test": {
        "defect": "test rows copied from train (vs. a repetitive population split at random)",
        "positive": homogeneity_positive, "negative": homogeneity_negative,
    },
    "resplit_falsification": {
        "defect": "label tied to flow groups the random split leaks",
        "positive": group_leak_positive, "negative": group_leak_negative,
    },
    "repeated_seed_falsification_check": {
        "defect": "label tied to flow groups the random split leaks (5 seeds)",
        "positive": group_leak_positive, "negative": group_leak_negative,
    },
    "result_robustness_check": {
        "defect": "label recoverable only from an identity column",
        "positive": robustness_positive, "negative": robustness_negative,
    },
}

# Checks run on imbalance_control: the first should react, the rest must not.
IMBALANCE_EXPECTED_FIRES = ["class_distribution_report"]
IMBALANCE_EXPECTED_CLEAN = [
    "dedup_check", "label_conflict_check", "near_duplicate_class_check", "one_rule_check",
    "row_order_leakage_check", "homogeneity_test", "feature_auc_ranking_check",
]
