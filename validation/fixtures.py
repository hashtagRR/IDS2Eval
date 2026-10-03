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
}
