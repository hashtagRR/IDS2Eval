import json

import pandas as pd
import yaml

from ids2eval.cli import main


def _latest_run_dir(output_dir):
    runs = sorted((output_dir / "runs").iterdir())
    return runs[-1]


def test_cli_end_to_end(tmp_path, synth_data):
    data_path = tmp_path / "data.csv"
    synth_data.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)],
                     "group_columns": ["SrcIP"], "split_ratio": 0.5},
        "schema": {"label_column": "Label", "id_like_columns": ["SrcIP"]},
        "classifiers": {"list": ["DecisionTree"]},
        "output": {"dir": str(output_dir)},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    main(["--config", str(config_path)])
    run_dir = _latest_run_dir(output_dir)

    assert (run_dir / "audit_report_before.json").exists()
    assert (run_dir / "audit_report_after.json").exists()  # preprocessing.dedup defaults true
    assert (run_dir / "train.parquet").exists()
    assert (run_dir / "test.parquet").exists()
    assert (run_dir / "benchmark_results.csv").exists()
    assert (run_dir / "benchmark_details.json").exists()
    assert (run_dir / "environment.json").exists()
    assert (run_dir / "resolved_config.json").exists()
    assert (run_dir / "scorecard.json").exists()
    assert (run_dir / "SCORECARD.md").exists()

    findings = json.loads((run_dir / "audit_report_before.json").read_text())
    assert len(findings) == 9  # all v1 checks (incl. data_integrity_check), v2 off by default

    after = json.loads((run_dir / "audit_report_after.json").read_text())
    dedup_after = next(f for f in after if f["check"] == "dedup_check")
    assert dedup_after["details"]["train_duplicates_dropped"] == 0  # already deduped by this point

    sc = json.loads((run_dir / "scorecard.json").read_text())
    assert sc["audit_stage"] == "after"  # preprocessing.dedup defaults true
    assert sc["overall_status"] in {"passed", "passed_with_warnings", "failed"}
    assert len(sc["findings"]) == len(after)
    assert sc["dataset_fingerprint"]["train_content_hash"]


def test_cli_second_run_loads_from_cache_not_raw_files(tmp_path, synth_data, monkeypatch):
    data_path = tmp_path / "data.csv"
    synth_data.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)],
                     "group_columns": ["SrcIP"], "split_ratio": 0.5},
        "schema": {"label_column": "Label", "id_like_columns": ["SrcIP"]},
        "audit": {"resplit_falsification": False},
        "classifiers": {"list": ["DecisionTree"]},
        "output": {"dir": str(output_dir)},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    main(["--config", str(config_path)])  # first run: populates the cache
    assert (output_dir / ".cache" / "manifest.json").exists()

    from ids2eval import dataset as dataset_module

    def _boom(cfg):
        raise AssertionError("load_split should not be called on a cache hit")

    monkeypatch.setattr(dataset_module, "load_split", _boom)
    main(["--config", str(config_path)])  # second run: must not touch raw_files
    assert len(list((output_dir / "runs").iterdir())) == 2  # two distinct run dirs, cache reused for both


def test_cli_applies_attack_type_mapping_before_audit_and_benchmark(tmp_path):
    import numpy as np
    rng = np.random.RandomState(0)
    n = 500
    attack_type = rng.choice(["Benign", "DoS-Hulk", "DoS-GoldenEye", "PortScan"], size=n)
    df = pd.DataFrame({
        "F1": rng.normal(0, 1, n),
        "F2": rng.normal(0, 1, n),
        "BinaryLabel": np.where(attack_type == "Benign", "Benign", "Attack"),
        "AttackType": attack_type,
    })
    data_path = tmp_path / "data.csv"
    df.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)]},
        "schema": {"label_column": "BinaryLabel", "attack_category_column": "AttackType"},
        "label_grouping": {"attack_type_mapping": {"DoS-Hulk": "DoS", "DoS-GoldenEye": "DoS"}},
        "audit": {"resplit_falsification": False},
        "classifiers": {"list": ["DecisionTree"]},
        "output": {"dir": str(output_dir)},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    main(["--config", str(config_path)])
    run_dir = _latest_run_dir(output_dir)

    train_out = pd.read_parquet(run_dir / "train.parquet")
    assert set(train_out["AttackType"].unique()) <= {"Benign", "DoS", "PortScan"}
    assert "DoS-Hulk" not in set(train_out["AttackType"].unique())

    findings = json.loads((run_dir / "audit_report_before.json").read_text())
    dist = next(f for f in findings if f["check"] == "class_distribution_report")
    assert set(dist["details"]["train"]["counts"]) <= {"Benign", "Attack"}  # binary stage's own column, unaffected

    results_df = pd.read_csv(run_dir / "benchmark_results.csv")
    assert "type" in set(results_df["stage"])


def test_cli_skip_flags(tmp_path, synth_data):
    data_path = tmp_path / "data.csv"
    synth_data.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)]},
        "schema": {"label_column": "Label"},
        "audit": {"resplit_falsification": False},
        "output": {"dir": str(output_dir), "save_preprocessed": False},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    main(["--config", str(config_path), "--skip-audit", "--skip-benchmark"])
    run_dir = _latest_run_dir(output_dir)

    assert not (run_dir / "audit_report_before.json").exists()
    assert not (run_dir / "benchmark_results.csv").exists()
    assert not (run_dir / "train.parquet").exists()
    assert not (run_dir / "scorecard.json").exists()  # nothing to score without an audit


def test_cli_hard_fails_on_disjoint_train_test_schema(tmp_path):
    # A reachable real-world case, unlike duplicate column names (pandas'
    # read_csv already auto-mangles those to F/F.1 before this code ever
    # sees the frame - see test_dataset.py for a direct unit test of that
    # branch instead). Disjoint schemas are real: e.g. two datasets
    # accidentally paired as train/test.
    train_path, test_path = tmp_path / "train.csv", tmp_path / "test.csv"
    train_path.write_text("Label,F1\nA,1\nB,2\n")
    test_path.write_text("Label,CompletelyDifferentColumn\nA,9\n")
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "train_file": str(train_path), "test_file": str(test_path)},
        "schema": {"label_column": "Label"},
        "audit": {"resplit_falsification": False},
        "output": {"dir": str(output_dir)},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    import pytest
    with pytest.raises(ValueError, match="share no feature columns"):
        main(["--config", str(config_path)])


def test_cli_keep_runs_prunes_old_run_directories(tmp_path, synth_data):
    data_path = tmp_path / "data.csv"
    synth_data.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)],
                     "group_columns": ["SrcIP"], "split_ratio": 0.5},
        "schema": {"label_column": "Label"},
        "audit": {"resplit_falsification": False},
        "classifiers": {"list": []},
        "output": {"dir": str(output_dir), "keep_runs": 2, "save_preprocessed": False},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    for _ in range(4):
        main(["--config", str(config_path)])

    assert len(list((output_dir / "runs").iterdir())) == 2


def test_cli_writes_dataset_fingerprint_and_completed_status(tmp_path, synth_data):
    data_path = tmp_path / "data.csv"
    synth_data.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)],
                     "group_columns": ["SrcIP"], "split_ratio": 0.5},
        "schema": {"label_column": "Label"},
        "audit": {"resplit_falsification": False},
        "classifiers": {"list": ["DecisionTree"]},
        "output": {"dir": str(output_dir)},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    main(["--config", str(config_path)])
    run_dir = _latest_run_dir(output_dir)

    assert (run_dir / "dataset_fingerprint.json").exists()
    status = json.loads((run_dir / "run_status.json").read_text())
    assert status["status"] == "completed"
    assert status["failed_stage"] is None


def test_cli_writes_failed_status_on_crash(tmp_path, synth_data, monkeypatch):
    data_path = tmp_path / "data.csv"
    synth_data.to_csv(data_path, index=False)
    output_dir = tmp_path / "output"

    config = {
        "dataset": {"name": "test-ds", "raw_files": [str(data_path)],
                     "group_columns": ["SrcIP"], "split_ratio": 0.5},
        "schema": {"label_column": "Label"},
        "audit": {"resplit_falsification": False},
        "classifiers": {"list": ["DecisionTree"]},
        "output": {"dir": str(output_dir)},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    def _boom(*a, **kw):
        raise RuntimeError("simulated benchmark crash")

    # cli.py does `from .benchmark import run_benchmark` - patch its own
    # bound name, not the source module's attribute, which wouldn't affect
    # the reference cli.py already holds.
    monkeypatch.setattr("ids2eval.cli.run_benchmark", _boom)

    import pytest
    with pytest.raises(RuntimeError, match="simulated benchmark crash"):
        main(["--config", str(config_path)])

    run_dir = _latest_run_dir(output_dir)
    status = json.loads((run_dir / "run_status.json").read_text())
    assert status["status"] == "failed"
    assert status["failed_stage"] == "benchmark"
    assert "simulated benchmark crash" in status["error"]
