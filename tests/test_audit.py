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
    label_conflict,
    leakage,
    one_rule,
    resplit,
    schema_fingerprint,
    seed_sensitivity,
    synthetic_realism,
    temporal_leakage,
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
    # the actual issue text and citation must be in the summary, not just a count
    assert "Brute-Force-Web" in result["summary"]
    assert "Liu et al. 2022" in result["summary"]


def test_known_issue_lookup_cic_ddos2019_has_two_curated_issues(base_cfg):
    base_cfg["dataset"]["name"] = "cic-ddos2019"
    result = known_issues.check(pd.DataFrame(), base_cfg)
    assert result["status"] == "warning"
    assert len(result["details"]["matches"]) == 2
    assert "Sharafaldin et al. 2019" in result["summary"]
    assert "UDP-lag" in result["summary"]


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


def _port_driven_split(base_cfg):
    rng = np.random.RandomState(0)
    port = rng.randint(0, 5, 600)
    label = np.array(["Benign", "DoS", "Scan"])[port % 3]
    train_df = pd.DataFrame({"DstPort": port, "F": rng.normal(size=600), "Label": label})
    test_df = train_df.iloc[300:].copy()
    cfg = dict(base_cfg, schema={**base_cfg["schema"], "id_like_columns": ["DstPort"]})
    return train_df, test_df, cfg


def test_identity_column_flag_survives_a_class_missing_from_test(base_cfg):
    # Real crash: CIC-IDS2018's rarest class landed only in train after reservoir sampling.
    train_df, test_df, cfg = _port_driven_split(base_cfg)
    train_df.loc[:2, "Label"] = "TrainOnly"
    result = identity_columns.check_predictive_power(train_df, test_df, cfg)
    assert result["status"] == "flag"
    assert result["details"]["standalone_auc"]["DstPort"] > 0.9


def test_identity_column_flag_survives_test_only_classes(base_cfg):
    # NSL-KDD holds attack types in test that never appear in train, by design.
    train_df, test_df, cfg = _port_driven_split(base_cfg)
    test_df.loc[test_df.index[:5], "Label"] = "TestOnly"
    result = identity_columns.check_predictive_power(train_df, test_df, cfg)
    assert result["status"] == "flag"
    assert result["details"]["standalone_auc"]["DstPort"] > 0.9


def test_robust_auc_matches_sklearn_when_class_sets_agree_and_none_when_undefined():
    from sklearn.metrics import roc_auc_score

    from ids2eval.audit._auc import robust_auc

    y = np.array(["a", "b", "c", "a", "b", "c"])
    proba = np.array([[.7, .2, .1], [.2, .6, .2], [.1, .3, .6], [.5, .4, .1], [.3, .3, .4], [.2, .2, .6]])
    expected = roc_auc_score(y, proba, multi_class="ovr", average="weighted")
    assert robust_auc(y, proba, ["a", "b", "c"]) == expected
    assert robust_auc(np.array(["a", "a"]), proba[:2], ["a", "b", "c"]) is None


def test_run_audit_skip_omits_exactly_the_requested_checks(base_cfg, synth_train_test):
    from ids2eval.audit import STRUCTURAL_CHECKS, run_audit

    train_df, test_df = synth_train_test
    findings = run_audit(train_df, test_df, base_cfg, skip=STRUCTURAL_CHECKS)
    checks = {f["check"] for f in findings}
    assert checks.isdisjoint(STRUCTURAL_CHECKS)
    # everything else that's enabled by default still ran
    assert "dedup_check" in checks and "leakage_screen" in checks


def test_structural_checks_constant_matches_the_checks_that_ignore_row_content():
    # A check belongs here only if no plausible row-content change (i.e. dedup) can move
    # its result - see each check's own module docstring/logic for why.
    from ids2eval.audit import STRUCTURAL_CHECKS

    assert STRUCTURAL_CHECKS == {"known_issue_lookup", "schema_fingerprint_check", "resplit_falsification"}


# -- label_conflict_check --------------------------------------------------

def test_label_conflict_check_flags_identical_features_different_labels(base_cfg):
    df = pd.DataFrame({
        "F1": [1.0, 1.0, 2.0, 3.0, 3.0],
        "Label": ["Benign", "Attack", "Benign", "Attack", "Attack"],
    })
    # rows 0/1 share F1=1.0 but disagree on label; rows 3/4 share F1=3.0 and agree
    train_df, test_df = df.iloc[:3], df.iloc[3:]
    result = label_conflict.check(train_df, test_df, base_cfg)
    assert result["status"] == "flag"
    assert result["details"]["conflicting_groups"] == 1
    assert result["details"]["conflicting_rows"] == 2
    assert "contradicts itself" in result["summary"]


def test_label_conflict_check_detects_cross_split_conflicts(base_cfg):
    train_df = pd.DataFrame({"F1": [1.0], "Label": ["Benign"]})
    test_df = pd.DataFrame({"F1": [1.0], "Label": ["Attack"]})
    result = label_conflict.check(train_df, test_df, base_cfg)
    assert result["status"] == "flag"
    assert result["details"]["cross_split_conflicting_groups"] == 1
    assert "span train and test" in result["summary"]


def test_label_conflict_check_ok_when_every_feature_vector_has_one_label(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = label_conflict.check(train_df, test_df, base_cfg)
    assert result["check"] == "label_conflict_check"
    assert result["status"] == "ok"


def test_label_conflict_check_is_masked_after_dedup(base_cfg):
    # Documents the real behavior described in the module docstring: dedup already
    # ignores the label column when grouping duplicates, so it collapses a conflict
    # to a single arbitrarily-kept row before this check ever sees it.
    from ids2eval.data import dataset

    df = pd.DataFrame({
        "F1": [1.0, 1.0, 2.0],
        "Label": ["Benign", "Attack", "Benign"],
    })
    train_df, test_df = df.iloc[:2], df.iloc[2:]
    train_deduped, test_deduped, _ = dataset.dedup(train_df.copy(), test_df.copy(), base_cfg)
    result = label_conflict.check(train_deduped, test_deduped, base_cfg)
    assert result["status"] == "ok"


# -- one_rule_check ---------------------------------------------------------

def test_one_rule_check_flags_a_trivially_separable_problem(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = one_rule.check(train_df, test_df, base_cfg)
    # synth_data's LeakyFeature perfectly separates Benign from everything else
    assert result["status"] == "flag"
    assert "LeakyFeature" in result["details"]["rule"]
    assert result["details"]["test_accuracy"] > 0.95


def test_one_rule_check_ok_when_no_single_feature_suffices(base_cfg):
    rng = np.random.RandomState(0)
    n = 400
    # XOR-like: no single threshold on either feature predicts the label well
    f1, f2 = rng.uniform(-1, 1, n), rng.uniform(-1, 1, n)
    label = np.where((f1 > 0) == (f2 > 0), "Benign", "Attack")
    df = pd.DataFrame({"F1": f1, "F2": f2, "Label": label})
    train_df, test_df = df.iloc[:300], df.iloc[300:]
    result = one_rule.check(train_df, test_df, base_cfg)
    assert result["status"] == "ok"
    assert result["details"]["test_accuracy"] < 0.95


# -- temporal_leakage_check ---------------------------------------------------

def test_temporal_leakage_check_ok_with_no_timestamp_column_configured(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    result = temporal_leakage.check(train_df, test_df, base_cfg)
    assert result["status"] == "ok"
    assert "no schema.timestamp_column configured" in result["summary"]


def test_temporal_leakage_check_flags_a_scenario_ordered_timestamp(base_cfg):
    # Contiguous same-label time blocks (the "run-to-failure bias" pattern from
    # Wu & Keogh 2021, reproducing this project's own CIC-IDS2018 finding - Timestamp
    # alone: AUC 0.93), then a RANDOM row-level split - matching how a real dataset's
    # random 80/20 split scatters both train and test rows throughout each attack's
    # collection window, rather than cutting the timeline into disjoint unseen chunks.
    from sklearn.model_selection import train_test_split

    rng = np.random.RandomState(0)
    n = 1200
    block = np.arange(n) // 50
    label = np.where(block % 2 == 0, "Benign", "Attack")
    ts = pd.date_range("2018-01-01", periods=n, freq="min").astype(str)
    df = pd.DataFrame({"F1": rng.normal(size=n), "Timestamp": ts, "Label": label})
    train_df, test_df = train_test_split(df, test_size=0.3, random_state=0, stratify=label)
    train_df, test_df = train_df.reset_index(drop=True), test_df.reset_index(drop=True)
    cfg = dict(base_cfg, schema={**base_cfg["schema"], "timestamp_column": "Timestamp"})
    result = temporal_leakage.check(train_df, test_df, cfg)
    assert result["status"] == "flag"
    assert result["details"]["standalone_auc"] > 0.8


def test_temporal_leakage_check_ok_when_timestamp_is_uninformative(base_cfg):
    rng = np.random.RandomState(0)
    n = 600
    label = rng.choice(["Benign", "Attack"], size=n)  # independent of time
    ts = pd.date_range("2018-01-01", periods=n, freq="min").astype(str)
    df = pd.DataFrame({"F1": rng.normal(size=n), "Timestamp": ts, "Label": label})
    train_df, test_df = df.iloc[:400], df.iloc[400:]
    cfg = dict(base_cfg, schema={**base_cfg["schema"], "timestamp_column": "Timestamp"})
    result = temporal_leakage.check(train_df, test_df, cfg)
    assert result["status"] == "ok"


# -- seed_sensitivity_check ---------------------------------------------------

def test_seed_sensitivity_check_ok_when_leakage_screen_is_clearly_and_stably_flagged(base_cfg, synth_train_test):
    # synth_data's LeakyFeature perfectly separates the label regardless of seed -
    # leakage_screen and one_rule_check should both flag on every seed, so the
    # *verdict* is stable even though it's a flag, not an ok, each time.
    train_df, test_df = synth_train_test
    result = seed_sensitivity.check(train_df, test_df, base_cfg)
    assert result["check"] == "seed_sensitivity_check"
    assert result["status"] == "ok"
    assert result["details"]["leakage_screen_statuses"] == ["flag"]
    assert result["details"]["one_rule_check_statuses"] == ["flag"]


def test_seed_sensitivity_check_flags_an_unstable_leakage_screen_verdict(base_cfg, monkeypatch):
    # Force leakage.check to answer "flag" on even seeds and "ok" on odd ones,
    # regardless of the data - isolates the check's own instability detection
    # from actually needing to engineer borderline real data.
    import pandas as pd

    from ids2eval.audit import seed_sensitivity as ss

    def fake_leakage_check(train_df, test_df, cfg, seed=0):
        status = "flag" if seed % 2 == 0 else "ok"
        return {"check": "leakage_screen", "status": status, "summary": "s",
                "details": {"top1_share": 0.4 + seed * 0.02}}

    monkeypatch.setattr(ss.leakage, "check", fake_leakage_check)
    df = pd.DataFrame({"F1": range(20), "Label": ["Benign", "Attack"] * 10})
    result = ss.check(df, df, base_cfg)
    assert result["status"] == "warning"
    assert result["details"]["leakage_screen_statuses"] == ["flag", "ok"]
    assert "leakage_screen" in result["summary"]


def test_label_conflict_check_groups_on_a_hash_key_not_raw_columns(base_cfg, monkeypatch):
    # Real OOM hit on CIC-IDS2017 (2.9M rows x 78 features): groupby on every compare
    # column directly exhausted memory on a 7.8GB VM. Pin the implementation to
    # hashing first, so a future edit can't silently reintroduce a wide groupby.
    import pandas as pd

    from ids2eval.audit import label_conflict as lc

    calls = []
    real_groupby = pd.DataFrame.groupby

    def spy_groupby(self, by, *args, **kwargs):
        calls.append(by)
        return real_groupby(self, by, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "groupby", spy_groupby)
    df = pd.DataFrame({"F1": [1.0, 1.0, 2.0], "F2": [1.0, 1.0, 2.0], "Label": ["Benign", "Attack", "Benign"]})
    lc.check(df.iloc[:2], df.iloc[2:], base_cfg)
    assert all(by == "_key" for by in calls)  # never grouped on the raw feature columns


def test_label_conflict_check_handles_many_feature_columns_without_blowing_up(base_cfg):
    # A moderate stand-in for the real ~2.9M-row x 78-column OOM: enough columns and
    # rows to make a raw multi-column groupby meaningfully more expensive than a
    # hashed single-key one, run in CI on every push rather than only by hand.
    import numpy as np
    import pandas as pd

    rng = np.random.RandomState(0)
    n, n_features = 20_000, 60
    data = {f"F{i}": rng.normal(size=n) for i in range(n_features)}
    data["Label"] = rng.choice(["Benign", "Attack"], size=n)
    df = pd.DataFrame(data)
    train_df, test_df = df.iloc[: n // 2].reset_index(drop=True), df.iloc[n // 2 :].reset_index(drop=True)
    result = label_conflict.check(train_df, test_df, base_cfg)
    assert result["check"] == "label_conflict_check"
    assert result["status"] in {"ok", "flag"}
