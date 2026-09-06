from ids2eval.benchmark import run_benchmark


def test_run_benchmark_binary_only(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree", "NaiveBayes"]
    results, extras = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["stage"]) == {"binary"}
    assert set(results["classifier"]) == {"DecisionTree", "NaiveBayes"}
    assert results["accuracy"].between(0, 1).all()
    assert "binary" in extras["class_distributions"]
    assert "original" in extras["class_distributions"]["binary"]


def test_run_benchmark_adds_type_stage_when_attack_category_set(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["schema"]["attack_category_column"] = "Label"  # reuse Label as a stand-in multi-class column
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    results, _extras = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["stage"]) == {"binary", "type"}


def test_run_benchmark_tuning_path(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    base_cfg["classifiers"]["tuning"] = True
    results, extras = run_benchmark(train_df, test_df, base_cfg)
    assert len(results) == 1
    detail = extras["binary|none|DecisionTree"]
    assert detail["best_params"] is not None  # GridSearchCV ran, so a winner was picked


def test_run_benchmark_skips_failing_classifier_without_crashing(base_cfg, synth_train_test, monkeypatch):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree", "NaiveBayes"]

    from ids2eval import classifiers as clf_registry
    original_build = clf_registry.build_estimator

    def _boom(name, overrides=None, seed=None):
        if name == "NaiveBayes":
            raise RuntimeError("simulated failure")
        return original_build(name, overrides, seed=seed)

    monkeypatch.setattr("ids2eval.benchmark.clf_registry.build_estimator", _boom)
    results, _extras = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["classifier"]) == {"DecisionTree"}


def test_run_benchmark_result_has_richer_columns(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    results, extras = run_benchmark(train_df, test_df, base_cfg)
    assert {"train_time_s", "infer_time_s", "sampling"} <= set(results.columns)

    detail = extras["binary|none|DecisionTree"]
    assert "confusion_matrix" in detail
    assert "per_class_report" in detail
    assert "feature_importance" in detail
    assert detail["feature_importance"] is not None  # DecisionTree supports feature_importances_


def test_run_benchmark_multiple_sampling_strategies_produce_separate_rows(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    base_cfg["preprocessing"]["sampling"]["binary"] = ["none", "smote"]
    results, extras = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["sampling"]) == {"none", "smote"}
    assert len(results) == 2
    dist = extras["class_distributions"]["binary"]
    assert "none" in dist and "smote" in dist
    # SMOTE should have balanced the classes; the untouched original shouldn't be
    assert len(set(dist["smote"].values())) == 1


def test_run_benchmark_scaling_and_sampling_are_fold_safe_under_tuning(base_cfg):
    # Regression test for the leakage fix: tuning + sampling must not raise
    # or silently double-resample - if scaling/sampling leaked in as
    # pre-transformed arrays, GridSearchCV's internal CV would either crash
    # (shape mismatch from an already-encoded/scaled input mismatching a
    # pipeline step) or behave inconsistently across folds. Uses its own
    # balanced 2-class fixture rather than synth_train_test's imbalanced
    # 3-class one - a rare class there is too small for SMOTE once split
    # further into CV folds, which is a real, separate constraint (SMOTE
    # needs enough per-fold minority samples) unrelated to what this test
    # is actually checking.
    import numpy as np
    import pandas as pd
    rng = np.random.RandomState(0)
    n = 300
    df = pd.DataFrame({
        "F1": rng.normal(0, 1, n), "F2": rng.normal(0, 1, n),
        "Label": rng.choice(["A", "B"], n, p=[0.8, 0.2]),
    })
    train_df, test_df = df.iloc[:200].reset_index(drop=True), df.iloc[200:].reset_index(drop=True)

    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    base_cfg["classifiers"]["tuning"] = True
    base_cfg["preprocessing"]["sampling"]["binary"] = "smote"
    results, _extras = run_benchmark(train_df, test_df, base_cfg)
    assert len(results) == 1
    assert results["accuracy"].iloc[0] is not None


def test_different_random_seed_changes_smote_output(base_cfg):
    # Proves random_seed actually reaches the sampler inside the pipeline,
    # not just that it's accepted as a config field.
    import numpy as np
    import pandas as pd
    rng = np.random.RandomState(1)
    n = 300
    df = pd.DataFrame({
        "F1": rng.normal(0, 1, n), "F2": rng.normal(0, 1, n),
        "Label": rng.choice(["A", "B"], n, p=[0.8, 0.2]),
    })
    train_df, test_df = df.iloc[:200].reset_index(drop=True), df.iloc[200:].reset_index(drop=True)
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    base_cfg["preprocessing"]["sampling"]["binary"] = "smote"

    base_cfg["random_seed"] = 0
    _, extras_a = run_benchmark(train_df, test_df, base_cfg)
    base_cfg["random_seed"] = 999
    _, extras_b = run_benchmark(train_df, test_df, base_cfg)

    fi_a = extras_a["binary|smote|DecisionTree"]["feature_importance"]
    fi_b = extras_b["binary|smote|DecisionTree"]["feature_importance"]
    assert fi_a != fi_b  # different synthetic SMOTE points -> different fitted tree


def test_same_random_seed_is_fully_reproducible(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    base_cfg["preprocessing"]["sampling"]["binary"] = "smote"

    results_a, extras_a = run_benchmark(train_df.copy(), test_df.copy(), base_cfg)
    results_b, extras_b = run_benchmark(train_df.copy(), test_df.copy(), base_cfg)

    assert results_a["accuracy"].tolist() == results_b["accuracy"].tolist()
    assert extras_a["binary|smote|DecisionTree"]["feature_importance"] == \
        extras_b["binary|smote|DecisionTree"]["feature_importance"]
