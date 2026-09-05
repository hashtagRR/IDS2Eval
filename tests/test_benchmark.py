from ids2eval.benchmark import run_benchmark


def test_run_benchmark_binary_only(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree", "NaiveBayes"]
    results = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["stage"]) == {"binary"}
    assert set(results["classifier"]) == {"DecisionTree", "NaiveBayes"}
    assert results["accuracy"].between(0, 1).all()


def test_run_benchmark_adds_type_stage_when_attack_category_set(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["schema"]["attack_category_column"] = "Label"  # reuse Label as a stand-in multi-class column
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    results = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["stage"]) == {"binary", "type"}


def test_run_benchmark_tuning_path(base_cfg, synth_train_test):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree"]
    base_cfg["classifiers"]["tuning"] = True
    results = run_benchmark(train_df, test_df, base_cfg)
    assert len(results) == 1


def test_run_benchmark_skips_failing_classifier_without_crashing(base_cfg, synth_train_test, monkeypatch):
    train_df, test_df = synth_train_test
    base_cfg["classifiers"]["list"] = ["DecisionTree", "NaiveBayes"]

    from ids2eval import classifiers as clf_registry
    original_build = clf_registry.build_estimator

    def _boom(name, overrides=None):
        if name == "NaiveBayes":
            raise RuntimeError("simulated failure")
        return original_build(name, overrides)

    monkeypatch.setattr("ids2eval.benchmark.clf_registry.build_estimator", _boom)
    results = run_benchmark(train_df, test_df, base_cfg)
    assert set(results["classifier"]) == {"DecisionTree"}
