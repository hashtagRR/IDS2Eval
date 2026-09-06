import numpy as np
import pandas as pd

from ids2eval.audit import (
    class_distribution,
    cross_dataset_drift,
    data_integrity,
    dedup,
    homogeneity,
    identity_columns,
    known_issues,
    leakage,
    resplit,
    schema_fingerprint,
    synthetic_realism,
)


def _add_id_like_column(cfg):
    cfg["schema"]["id_like_columns"] = ["SrcIP"]
    return cfg


# -- v1 checks -----------------------------------------------------------

def test_dedup_check_flags_planted_duplicates(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = dedup.check(train_df, test_df, base_cfg)
    assert result["check"] == "dedup_check"
    # planted duplicates land mostly in train after the stratified split
    assert result["details"]["train_duplicates_dropped"] + result["details"]["test_leakage_dropped"] > 0


def test_leakage_screen_flags_the_planted_leaky_feature(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = leakage.check(train_df, test_df, base_cfg)
    assert result["status"] == "flag"
    assert "LeakyFeature" in result["details"]["top_features"]


def test_leakage_screen_ok_when_no_feature_dominates(base_cfg):
    rng = np.random.RandomState(0)
    n = 500
    df = pd.DataFrame({
        "F1": rng.normal(0, 1, n), "F2": rng.normal(0, 1, n), "F3": rng.normal(0, 1, n),
        "Label": rng.choice(["A", "B"], n),
    })
    train_df, test_df = df.iloc[:350].reset_index(drop=True), df.iloc[350:].reset_index(drop=True)
    result = leakage.check(train_df, test_df, base_cfg)
    assert result["status"] == "ok"


def test_identity_column_flag_detects_predictive_ip(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    cfg = _add_id_like_column(base_cfg)
    result = identity_columns.check_predictive_power(train_df, test_df, cfg)
    assert result["status"] == "flag"
    assert "SrcIP" in result["details"]["suggested_drop"]


def test_low_cardinality_warning_on_two_unique_ips(base_cfg, synth_train_test):
    train_df, _ = synth_train_test
    cfg = _add_id_like_column(base_cfg)
    result = identity_columns.check_cardinality(train_df, cfg)
    assert result["status"] == "warning"
    assert result["details"]["cardinalities"]["SrcIP"] == 2


def test_identity_checks_ok_with_no_id_like_columns(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    assert identity_columns.check_predictive_power(train_df, test_df, base_cfg)["status"] == "ok"
    assert identity_columns.check_cardinality(train_df, base_cfg)["status"] == "ok"


def test_homogeneity_test_runs_and_returns_per_class_stats(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = homogeneity.check(train_df, test_df, base_cfg)
    assert result["check"] == "homogeneity_test"
    assert len(result["details"]["per_class"]) >= 1


def test_resplit_falsification_end_to_end(base_cfg, tmp_path, synth_data):
    csv_path = tmp_path / "raw.csv"
    synth_data.to_csv(csv_path, index=False)
    base_cfg["dataset"]["raw_files"] = [str(csv_path)]
    base_cfg["dataset"]["group_columns"] = ["SrcIP"]
    base_cfg["dataset"]["split_ratio"] = 0.5  # synth_data only has 2 SrcIP groups
    result = resplit.check(base_cfg)
    assert result["check"] == "resplit_falsification"
    assert 0.0 <= result["details"]["random_accuracy"] <= 1.0
    assert 0.0 <= result["details"]["grouped_accuracy"] <= 1.0


def test_class_distribution_report_flags_rare_class(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = class_distribution.check(train_df, test_df, base_cfg)
    assert result["status"] == "warning"
    assert "Rare" in result["details"]["rare_classes"]


def test_schema_fingerprint_matches_cicflowmeter_columns(base_cfg):
    cols = ["Flow Duration", "Fwd Packet Length Mean", "Bwd Packet Length Mean",
            "Flow Bytes/s", "Flow Packets/s", "Fwd IAT Mean", "Bwd IAT Mean"]
    df = pd.DataFrame({c: [1] for c in cols})
    result = schema_fingerprint.check(df, base_cfg)
    assert result["status"] == "warning"
    assert "CICFlowMeter" in result["details"]


def test_schema_fingerprint_no_match_on_unrelated_columns(base_cfg):
    df = pd.DataFrame({"a": [1], "b": [2]})
    result = schema_fingerprint.check(df, base_cfg)
    assert result["status"] == "ok"


# -- v2 checks -------------------------------------------------------------

def test_known_issue_lookup_matches_substring(base_cfg):
    base_cfg["dataset"]["name"] = "CIC-IDS2018-corrected"
    result = known_issues.check(pd.DataFrame(), base_cfg)
    assert result["status"] == "warning"
    assert len(result["details"]["matches"]) == 1


def test_known_issue_lookup_no_match(base_cfg):
    base_cfg["dataset"]["name"] = "some-other-dataset"
    result = known_issues.check(pd.DataFrame(), base_cfg)
    assert result["status"] == "ok"


def test_synthetic_realism_check_flags_shifted_reference(base_cfg, tmp_path, synth_data):
    # reference sample with a clearly different LeakyFeature distribution
    ref_df = synth_data.copy()
    ref_df["LeakyFeature"] = ref_df["LeakyFeature"] + 500
    ref_path = tmp_path / "ref.csv"
    ref_df.to_csv(ref_path, index=False)
    base_cfg["audit"]["reference_dataset"] = str(ref_path)

    result = synthetic_realism.check(synth_data, base_cfg)
    assert result["status"] == "flag"
    assert result["details"]["domain_auc"] > 0.9


def test_cross_dataset_drift_check_runs(base_cfg, tmp_path, synth_train_test, synth_data):
    train_df, test_df = synth_train_test
    ref_path = tmp_path / "ref.csv"
    synth_data.to_csv(ref_path, index=False)
    base_cfg["audit"]["reference_dataset"] = str(ref_path)

    result = cross_dataset_drift.check(train_df, test_df, base_cfg)
    assert result["check"] == "cross_dataset_drift_check"
    assert "drop" in result["details"]


def test_cross_dataset_drift_warns_on_missing_label_column(base_cfg, tmp_path, synth_train_test):
    train_df, test_df = synth_train_test
    ref_path = tmp_path / "ref.csv"
    pd.DataFrame({"F1": [1, 2]}).to_csv(ref_path, index=False)
    base_cfg["audit"]["reference_dataset"] = str(ref_path)

    result = cross_dataset_drift.check(train_df, test_df, base_cfg)
    assert result["status"] == "warning"


# -- data_integrity_check ---------------------------------------------------

def test_data_integrity_flags_missing_label(base_cfg):
    df = pd.DataFrame({"F1": [1, 2, 3], "Label": ["A", None, "B"]})
    result = data_integrity.check(df, base_cfg)
    assert result["status"] == "flag"
    assert result["details"]["missing_label_count"] == 1


def test_data_integrity_warns_on_missing_feature_values(base_cfg):
    df = pd.DataFrame({"F1": [1, None, 3], "Label": ["A", "B", "A"]})
    result = data_integrity.check(df, base_cfg)
    assert result["status"] == "warning"
    assert result["details"]["missing_by_feature"] == {"F1": 1}


def test_data_integrity_warns_on_inf_values(base_cfg):
    df = pd.DataFrame({"F1": [1.0, np.inf, -np.inf], "Label": ["A", "B", "A"]})
    result = data_integrity.check(df, base_cfg)
    assert result["status"] == "warning"
    assert result["details"]["inf_by_feature"] == {"F1": 2}


def test_data_integrity_warns_on_constant_feature(base_cfg):
    df = pd.DataFrame({"F1": [5, 5, 5], "F2": [1, 2, 3], "Label": ["A", "B", "A"]})
    result = data_integrity.check(df, base_cfg)
    assert result["status"] == "warning"
    assert "F1" in result["details"]["constant_features"]
    assert "F2" not in result["details"]["constant_features"]


def test_data_integrity_ok_on_healthy_data(base_cfg):
    df = pd.DataFrame({"F1": [1, 2, 3, 4], "F2": [4, 3, 2, 1], "Label": ["A", "B", "A", "B"]})
    result = data_integrity.check(df, base_cfg)
    assert result["status"] == "ok"
