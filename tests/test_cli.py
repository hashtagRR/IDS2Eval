import json

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
