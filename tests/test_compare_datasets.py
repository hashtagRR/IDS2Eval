import yaml

from ids2eval.reporting import compare_datasets


def _write_config(tmp_path, name, data_path, split_ratio=0.5):
    config = {
        "dataset": {"name": name, "raw_files": [str(data_path)], "split_ratio": split_ratio},
        "schema": {"label_column": "Label"},
        "audit": {"resplit_falsification": False},
        "output": {"dir": str(tmp_path / f"output-{name}")},
    }
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.dump(config))
    return path


def test_compare_identical_datasets_is_equivalent(tmp_path):
    data_path = tmp_path / "data.csv"
    data_path.write_text("F1,Label\n" + "".join(f"{i},{'A' if i % 2 else 'B'}\n" for i in range(40)))

    config_a = _write_config(tmp_path, "a", data_path)
    config_b = _write_config(tmp_path, "b", data_path)

    result = compare_datasets.compare(str(config_a), str(config_b))
    assert result["schema_match"] is True
    assert result["combined_content_match"] is True
    assert result["row_count_match"] is True
    assert result["label_distribution_match"] is True

    report = compare_datasets.render_report(result)
    assert "PASS" in report
    assert "Equivalent" in report
    assert "FAIL" not in report


def test_compare_datasets_with_different_schema(tmp_path):
    data_a = tmp_path / "a.csv"
    data_a.write_text("F1,Label\n" + "".join(f"{i},{'A' if i % 2 else 'B'}\n" for i in range(40)))
    data_b = tmp_path / "b.csv"
    data_b.write_text("F1,F2,Label\n" + "".join(f"{i},{i},{'A' if i % 2 else 'B'}\n" for i in range(40)))

    config_a = _write_config(tmp_path, "a", data_a)
    config_b = _write_config(tmp_path, "b", data_b)

    result = compare_datasets.compare(str(config_a), str(config_b))
    assert result["schema_match"] is False
    assert result["columns_only_in_b"] == ["F2"]

    report = compare_datasets.render_report(result)
    assert "FAIL" in report
    assert "non-equivalent" in report


def test_compare_datasets_with_different_row_counts_but_same_schema(tmp_path):
    data_a = tmp_path / "a.csv"
    data_a.write_text("F1,Label\n" + "".join(f"{i},{'A' if i % 2 else 'B'}\n" for i in range(40)))
    data_b = tmp_path / "b.csv"
    data_b.write_text("F1,Label\n" + "".join(f"{i},{'A' if i % 2 else 'B'}\n" for i in range(60)))

    config_a = _write_config(tmp_path, "a", data_a)
    config_b = _write_config(tmp_path, "b", data_b)

    result = compare_datasets.compare(str(config_a), str(config_b))
    assert result["schema_match"] is True
    assert result["row_count_match"] is False
    assert result["combined_content_match"] is False
    assert result["row_count_a"] == 40
    assert result["row_count_b"] == 60
