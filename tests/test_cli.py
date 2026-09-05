import json

import pandas as pd
import yaml

from ids2eval.cli import main


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

    assert (output_dir / "audit_report.json").exists()
    assert (output_dir / "train.parquet").exists()
    assert (output_dir / "test.parquet").exists()
    assert (output_dir / "benchmark_results.csv").exists()

    findings = json.loads((output_dir / "audit_report.json").read_text())
    assert len(findings) == 8  # all v1 checks, v2 checks off by default


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

    train_out = pd.read_parquet(output_dir / "train.parquet")
    assert set(train_out["AttackType"].unique()) <= {"Benign", "DoS", "PortScan"}
    assert "DoS-Hulk" not in set(train_out["AttackType"].unique())

    findings = json.loads((output_dir / "audit_report.json").read_text())
    dist = next(f for f in findings if f["check"] == "class_distribution_report")
    assert set(dist["details"]["train"]["counts"]) <= {"Benign", "Attack"}  # binary stage's own column, unaffected

    results_df = pd.read_csv(output_dir / "benchmark_results.csv")
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

    assert not (output_dir / "audit_report.json").exists()
    assert not (output_dir / "benchmark_results.csv").exists()
    assert not (output_dir / "train.parquet").exists()
