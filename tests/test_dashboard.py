import json
import threading
import urllib.error
import urllib.request

import pytest

from ids2eval.dashboard import server as dashboard


@pytest.fixture
def server(tmp_path):
    run_dir = tmp_path / "out" / "runs" / "2026-01-01_000000_000000"
    run_dir.mkdir(parents=True)
    (run_dir / "scorecard.json").write_text(json.dumps({"dataset_name": "ds", "overall_status": "passed"}))
    (run_dir / "run_status.json").write_text(json.dumps({"status": "completed"}))
    (run_dir / "SCORECARD.html").write_text("<!doctype html><p>card</p>")
    (run_dir / "benchmark_results.csv").write_text("stage,classifier,f1_weighted\nbinary,DecisionTree,0.9\n")
    (tmp_path / "secret.txt").write_text("secret")

    app = dashboard.App([tmp_path / "out"], "dataset: {}\n")
    srv = dashboard.make_server("127.0.0.1", 0, app)
    port = srv.server_address[1]
    srv.RequestHandlerClass.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}", app
    srv.shutdown()
    srv.server_close()


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(url, body, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_lists_runs_with_verdict_and_serves_page(server):
    base, _ = server
    status, body = _get(base + "/api/runs")
    runs = json.loads(body)
    assert status == 200
    assert runs[0]["id"] == "0/2026-01-01_000000_000000"
    assert runs[0]["verdict"] == "passed"
    assert _get(base + "/")[0] == 200
    assert _get(base + "/static/app.js")[0] == 200
    assert _get(base + "/static/style.css")[0] == 200
    assert _get(base + "/static/..%2F..%2Fconfig.py")[0] == 404


def test_run_detail_includes_benchmark_rows(server):
    base, _ = server
    detail = json.loads(_get(base + "/api/run/0/2026-01-01_000000_000000")[1])
    assert detail["benchmark"] == [{"stage": "binary", "classifier": "DecisionTree", "f1_weighted": "0.9"}]


def test_serves_run_files_but_not_outside_the_run_dir(server):
    base, _ = server
    assert _get(base + "/files/0/2026-01-01_000000_000000/SCORECARD.html")[0] == 200
    assert _get(base + "/files/0/..%2F..%2Fsecret.txt/x")[0] == 404
    assert _get(base + "/files/0/2026-01-01_000000_000000/..%2F..%2F..%2Fsecret.txt")[0] == 404
    assert _get(base + "/api/run/7/2026-01-01_000000_000000")[0] == 404


def test_rejects_foreign_host_header(server):
    base, _ = server
    assert _get(base + "/api/runs", {"Host": "attacker.example:80"})[0] == 403


def test_rejects_cross_origin_and_non_json_posts(server):
    base, _ = server
    assert _post(base + "/api/validate", {"yaml": "x: 1"}, {"Origin": "http://attacker.example"})[0] == 403
    req = urllib.request.Request(base + "/api/run", data=b"yaml=x", method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 415


def test_validate_uses_the_real_config_validation(server):
    base, _ = server
    status, body = _post(base + "/api/validate", {"yaml": "random_seed: not-a-number\n"})
    assert status == 200 and body["ok"] is False and "random_seed" in body["error"]
    status, body = _post(base + "/api/run", {"yaml": ""})
    assert status == 400


def test_refuses_a_second_run_while_one_is_active(server):
    base, app = server
    app.job.state = "running"
    status, _ = _post(base + "/api/run", {"yaml": "dataset: {}\n"})
    assert status == 409


def test_citation_endpoint_matches_cli_bibtex(server, tmp_path):
    base, app = server
    run_dir = app.output_dirs[0] / "runs" / "2026-01-01_000000_000000"
    full_scorecard = {
        "dataset_name": "ds", "overall_status": "passed", "generated_at": "2026-01-01T00:00:00+00:00",
        "ids2eval_version": "0.1.0", "ids2eval_git_commit": "abc123", "scorecard_schema_version": "1.2",
        "dataset_fingerprint": {"train_content_hash": "deadbeef" * 4, "test_content_hash": "beefdead" * 4},
    }
    (run_dir / "scorecard.json").write_text(json.dumps(full_scorecard))

    from ids2eval.reporting import cite
    expected = cite.citation_bibtex(full_scorecard)

    status, body = _get(base + "/api/run/0/2026-01-01_000000_000000/citation")
    assert status == 200
    assert json.loads(body)["bibtex"] == expected


def test_citation_endpoint_404s_without_a_scorecard(server):
    base, _ = server
    assert _get(base + "/api/run/7/2026-01-01_000000_000000/citation")[0] == 404


def test_compare_datasets_endpoint_reports_equivalent_configs(server, tmp_path):
    base, _ = server
    data_path = tmp_path / "data.csv"
    data_path.write_text("F1,Label\n" + "".join(f"{i},{'A' if i % 2 else 'B'}\n" for i in range(40)))
    config = (
        f"dataset:\n  name: x\n  raw_files: [{data_path}]\n"
        "schema:\n  label_column: Label\naudit:\n  resplit_falsification: false\n"
    )

    status, body = _post(base + "/api/compare-datasets", {"yaml_a": config, "yaml_b": config})
    assert status == 200
    assert body["result"]["combined_content_match"] is True
    assert "Equivalent" in body["report"]


def test_compare_datasets_endpoint_requires_both_configs(server):
    base, _ = server
    status, _ = _post(base + "/api/compare-datasets", {"yaml_a": "dataset: {}\n", "yaml_b": ""})
    assert status == 400


def test_starter_config_is_the_full_schema_reference():
    # The New run editor should show every field, not a stripped-down subset -
    # this is configs/schema.yaml's own content, patched only where its true
    # default would otherwise trip a wall on the very first run (see below).
    assert dashboard._STARTER_CONFIG == dashboard._build_starter_config()
    assert "classifiers:" in dashboard._STARTER_CONFIG
    assert "write_scorecard_plot" in dashboard._STARTER_CONFIG


def test_starter_config_only_fails_on_fields_a_user_must_actually_supply():
    # Regression test: a user editing just name/raw_files/label_column in the New
    # run editor must not also hit audit.resplit_falsification's group_columns
    # requirement, the most common way a brand-new config used to fail validation.
    _, err = dashboard._validate(dashboard._STARTER_CONFIG)
    assert err is not None
    assert "resplit_falsification" not in err
    assert "dataset.name is required" in err
    assert "schema.label_column is required" in err

    text = dashboard._STARTER_CONFIG
    text = text.replace("name: null", "name: my-dataset", 1)
    text = text.replace("raw_files: []", "raw_files: [data.csv]", 1)
    text = text.replace("label_column: null", "label_column: Label", 1)
    cfg, err = dashboard._validate(text)
    assert cfg is not None, err


def test_build_starter_config_falls_back_when_schema_yaml_is_unreachable(monkeypatch):
    monkeypatch.setattr(dashboard, "_SCHEMA_YAML_PATH", dashboard.Path("/no/such/file.yaml"))
    assert dashboard._build_starter_config() == dashboard._MINIMAL_STARTER_CONFIG


def test_build_starter_config_falls_back_if_the_resplit_comment_drifts(monkeypatch, tmp_path, caplog):
    drifted = tmp_path / "schema.yaml"
    drifted.write_text("audit:\n  resplit_falsification: true  # wording changed\n")
    monkeypatch.setattr(dashboard, "_SCHEMA_YAML_PATH", drifted)
    assert dashboard._build_starter_config() == dashboard._MINIMAL_STARTER_CONFIG
    assert "changed" in caplog.text


def test_resolve_starter_with_no_config_uses_the_starter_template():
    starter, output_dirs = dashboard._resolve_starter(None, [])
    assert starter == dashboard._STARTER_CONFIG
    assert output_dirs == [dashboard.Path("./output")]


def test_resolve_starter_falls_back_instead_of_crashing_on_a_missing_file(tmp_path, caplog):
    missing = tmp_path / "does-not-exist.yaml"
    starter, output_dirs = dashboard._resolve_starter(str(missing), [])
    assert starter == dashboard._STARTER_CONFIG
    assert output_dirs == [dashboard.Path("./output")]
    assert "isn't readable" in caplog.text


def test_resolve_starter_loads_a_real_config_and_adds_its_output_dir(tmp_path):
    config_path = tmp_path / "cfg.yaml"
    output_dir = tmp_path / "myoutput"
    config_path.write_text(
        f"dataset:\n  name: x\n  raw_files: [a.csv]\nschema:\n  label_column: Label\n"
        f"audit:\n  resplit_falsification: false\noutput:\n  dir: {output_dir}\n"
    )
    starter, output_dirs = dashboard._resolve_starter(str(config_path), [])
    assert starter == config_path.read_text()
    assert output_dirs == [output_dir]


def test_recommendations_endpoint_reads_a_real_run(server):
    base, app = server
    run_dir = app.output_dirs[0] / "runs" / "2026-01-01_000000_000000"
    cfg = {"dataset": {"raw_files": ["a.csv"]}, "schema": {"drop_columns": []}, "audit": {}}
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg))
    findings = [{"check": "identity_column_flag", "status": "flag",
                 "summary": "s", "details": {"suggested_drop": ["SrcIP"]}}]
    (run_dir / "audit_report_after.json").write_text(json.dumps(findings))

    status, body = _get(base + "/api/run/0/2026-01-01_000000_000000/recommendations")
    assert status == 200
    recs = json.loads(body)["recommendations"]
    assert recs[0]["id"] == "drop_flagged_columns"
    assert recs[0]["patch"]["schema"]["drop_columns"] == ["SrcIP"]


def test_recommendations_endpoint_404s_without_a_resolved_config(server):
    base, _ = server
    assert _get(base + "/api/run/0/2026-01-01_000000_000000/recommendations")[0] == 404


def test_apply_recommendations_endpoint_merges_selected_patches(server):
    base, app = server
    run_dir = app.output_dirs[0] / "runs" / "2026-01-01_000000_000000"
    cfg = {"dataset": {"raw_files": ["a.csv"]}, "schema": {"drop_columns": []}, "audit": {}}
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg))
    findings = [{"check": "identity_column_flag", "status": "flag",
                 "summary": "s", "details": {"suggested_drop": ["SrcIP"]}}]
    (run_dir / "audit_report_after.json").write_text(json.dumps(findings))

    status, body = _post(base + "/api/run/0/2026-01-01_000000_000000/apply-recommendations",
                          {"ids": ["drop_flagged_columns"]})
    assert status == 200
    assert "SrcIP" in body["yaml"]


def test_apply_recommendations_endpoint_with_no_ids_returns_the_original_config(server):
    base, app = server
    run_dir = app.output_dirs[0] / "runs" / "2026-01-01_000000_000000"
    cfg = {"dataset": {"raw_files": ["a.csv"]}, "schema": {"drop_columns": []}, "audit": {}}
    (run_dir / "resolved_config.json").write_text(json.dumps(cfg))
    (run_dir / "audit_report_after.json").write_text(json.dumps([]))

    status, body = _post(base + "/api/run/0/2026-01-01_000000_000000/apply-recommendations", {"ids": []})
    assert status == 200
    assert "SrcIP" not in body["yaml"]
