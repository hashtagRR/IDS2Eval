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
