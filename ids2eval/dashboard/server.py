"""The IDS2Eval dashboard's server: browse runs, read scorecards, launch runs.

    ids2eval-dashboard --output ./output     # then open http://127.0.0.1:8765

The page itself lives next to this file, in static/ (index.html, style.css,
app.js) - plain files, served as-is, so they can be opened and edited
directly. See README.md in this folder for the endpoints and troubleshooting.

Standard library only (http.server), so it adds no dependencies. A run is
launched as a real `python -m ids2eval` subprocess - exactly what the CLI
does - so the UI can't drift from the CLI's behavior; it only writes the
YAML to a temp file and streams the log back.

Local by design: it binds to 127.0.0.1, and every request must carry a
localhost Host header (blocks DNS rebinding) and every POST a JSON body
from a same-origin page (blocks a random website from POSTing a config
that reads arbitrary files). Anyone who can reach the port can run a
config, so don't bind it to a public interface.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
import tempfile
import threading
import webbrowser
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import run_manager
from ..config import load_config

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
_LOG_LINES = 2000
_MAX_BODY = 1_000_000
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".parquet": "application/octet-stream",
}
_STARTER_CONFIG = """\
# Minimal config - every other field falls back to its default.
# The full, commented schema is configs/schema.yaml in the repo.
dataset:
  name: my-dataset
  raw_files: [path/to/data.csv]     # or train_file + test_file
schema:
  label_column: Label
classifiers:
  list: [DecisionTree, RandomForest]
output:
  dir: ./output
"""


class Job:
    """At most one run at a time: runs are CPU/RAM heavy, and two sharing
    one output.dir would race on the load-cache.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.log: deque[str] = deque(maxlen=_LOG_LINES)
        self.state = "idle"
        self.returncode: int | None = None
        self.output_dir: str | None = None

    def start(self, config_path: Path, output_dir: Path, skip_audit: bool, skip_benchmark: bool) -> None:
        cmd = [sys.executable, "-m", "ids2eval", "--config", str(config_path)]
        if skip_audit:
            cmd.append("--skip-audit")
        if skip_benchmark:
            cmd.append("--skip-benchmark")
        self.log.clear()
        self.log.append("$ " + " ".join(cmd))
        self.proc = subprocess.Popen(  # noqa: S603 - argv list, no shell; config was validated first
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        self.state, self.returncode, self.output_dir = "running", None, str(output_dir)
        threading.Thread(target=self._pump, args=(self.proc, config_path), daemon=True).start()

    def _pump(self, proc: subprocess.Popen, config_path: Path) -> None:
        for line in proc.stdout:
            self.log.append(line.rstrip("\n"))
        proc.wait()
        with self.lock:
            self.returncode = proc.returncode
            self.state = "completed" if proc.returncode == 0 else "failed"
        config_path.unlink(missing_ok=True)

    def snapshot(self) -> dict:
        return {"state": self.state, "returncode": self.returncode, "output_dir": self.output_dir,
                "log": list(self.log)}


class App:
    def __init__(self, output_dirs: list[Path], starter_config: str):
        self.output_dirs = [p.resolve() for p in output_dirs]
        self.starter_config = starter_config
        self.job = Job()

    def add_output_dir(self, path: Path) -> None:
        path = path.resolve()
        if path not in self.output_dirs:
            self.output_dirs.append(path)

    def run_dir(self, dir_idx: str, run_name: str) -> Path | None:
        if not dir_idx.isdigit() or int(dir_idx) >= len(self.output_dirs):
            return None
        runs_root = self.output_dirs[int(dir_idx)] / run_manager.RUNS_DIRNAME
        candidate = (runs_root / run_name).resolve()
        if candidate.parent != runs_root.resolve() or not candidate.is_dir():
            return None
        return candidate

    def list_runs(self) -> list[dict]:
        runs = []
        for idx, out in enumerate(self.output_dirs):
            runs_root = out / run_manager.RUNS_DIRNAME
            if not runs_root.is_dir():
                continue
            for run_dir in runs_root.iterdir():
                if run_dir.is_dir():
                    runs.append(_run_summary(idx, out, run_dir))
        return sorted(runs, key=lambda r: r["name"], reverse=True)


def _read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _run_summary(idx: int, output_dir: Path, run_dir: Path) -> dict:
    sc = _read_json(run_dir / "scorecard.json") or {}
    status = _read_json(run_dir / "run_status.json") or {}
    cfg = _read_json(run_dir / "resolved_config.json") or {}
    return {
        "id": f"{idx}/{run_dir.name}",
        "name": run_dir.name,
        "output_dir": str(output_dir),
        "dataset": sc.get("dataset_name") or cfg.get("dataset", {}).get("name"),
        "run_status": status.get("status", "running"),
        "failed_stage": status.get("failed_stage"),
        "error": status.get("error"),
        "verdict": sc.get("overall_status"),
        "files": sorted(p.name for p in run_dir.iterdir() if p.is_file()),
    }


def _benchmark_rows(run_dir: Path) -> list[dict]:
    path = run_dir / "benchmark_results.csv"
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


class Handler(BaseHTTPRequestHandler):
    app: App
    allowed_hosts: set[str]

    def log_message(self, fmt, *args):
        logger.debug("%s - %s", self.address_string(), fmt % args)

    def _host_ok(self) -> bool:
        return (self.headers.get("Host") or "") in self.allowed_hosts

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def do_GET(self):
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "bad Host header")
        path = unquote(urlsplit(self.path).path)
        if path == "/" or path.startswith("/static/"):
            return self._static("index.html" if path == "/" else path.removeprefix("/static/"))
        if path == "/api/runs":
            return self._json(self.app.list_runs())
        if path == "/api/job":
            return self._json(self.app.job.snapshot())
        if path == "/api/starter-config":
            return self._json({"yaml": self.app.starter_config})

        parts = path.strip("/").split("/")
        # /api/run/<dir_idx>/<run_name> - one run's detail
        if len(parts) == 4 and parts[:2] == ["api", "run"]:
            run_dir = self.app.run_dir(parts[2], parts[3])
            if run_dir is None:
                return self._error(HTTPStatus.NOT_FOUND, "no such run")
            summary = _run_summary(int(parts[2]), self.app.output_dirs[int(parts[2])], run_dir)
            return self._json({**summary, "scorecard": _read_json(run_dir / "scorecard.json"),
                               "benchmark": _benchmark_rows(run_dir)})
        # /files/<dir_idx>/<run_name>/<file> - a run artifact, top level of the run dir only
        if len(parts) == 4 and parts[0] == "files":
            run_dir = self.app.run_dir(parts[1], parts[2])
            target = run_dir / parts[3] if run_dir else None
            if target is None or "/" in parts[3] or parts[3].startswith(".") or not target.is_file():
                return self._error(HTTPStatus.NOT_FOUND, "no such file")
            ctype = _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
            extra = {}
            if target.suffix.lower() == ".html":
                # Only the scorecard's own inline styles - no scripts, nothing external.
                extra["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'"
            elif ctype == "application/octet-stream":
                extra["Content-Disposition"] = f'attachment; filename="{target.name}"'
            return self._send(HTTPStatus.OK, target.read_bytes(), ctype, extra)
        return self._error(HTTPStatus.NOT_FOUND, "not found")

    def _static(self, name: str) -> None:
        # Only files directly inside static/ - no subdirectories, no dotfiles, no "..".
        target = STATIC_DIR / name
        if "/" in name or name.startswith(".") or not target.is_file():
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        ctype = _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        extra = {}
        if target.suffix == ".html":
            # Everything is a same-origin file now, so no inline script/style is allowed at all.
            extra["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return self._send(HTTPStatus.OK, target.read_bytes(), ctype, extra)

    def do_POST(self):
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "bad Host header")
        origin = self.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc not in self.allowed_hosts:
            return self._error(HTTPStatus.FORBIDDEN, "cross-origin request refused")
        # A JSON content type can't be sent cross-site without a CORS preflight, which this server never approves.
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "expected application/json")
        length = int(self.headers.get("Content-Length") or 0)
        if length > _MAX_BODY:
            return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body too large")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._error(HTTPStatus.BAD_REQUEST, "invalid JSON")

        path = urlsplit(self.path).path
        if path == "/api/validate":
            cfg, err = _validate(body.get("yaml", ""))
            return self._json({"ok": err is None, "error": err,
                               "output_dir": cfg["output"]["dir"] if cfg else None})
        if path == "/api/run":
            return self._start_run(body)
        if path == "/api/job/stop":
            job = self.app.job
            with job.lock:
                if job.state == "running" and job.proc is not None:
                    job.proc.terminate()
                    job.log.append("[stopped from the web UI]")
            return self._json(job.snapshot())
        return self._error(HTTPStatus.NOT_FOUND, "not found")

    def _start_run(self, body: dict) -> None:
        job = self.app.job
        with job.lock:
            if job.state == "running":
                return self._error(HTTPStatus.CONFLICT, "a run is already in progress")
            cfg, err = _validate(body.get("yaml", ""))
            if err:
                return self._error(HTTPStatus.BAD_REQUEST, err)
            fd, name = tempfile.mkstemp(prefix="ids2eval-ui-", suffix=".yaml")
            with open(fd, "w") as f:
                f.write(body["yaml"])
            output_dir = Path(cfg["output"]["dir"])
            self.app.add_output_dir(output_dir)
            job.start(Path(name), output_dir, bool(body.get("skip_audit")), bool(body.get("skip_benchmark")))
        return self._json(job.snapshot())


def _validate(yaml_text: str) -> tuple[dict | None, str | None]:
    """The same load_config() the CLI runs, so a config the UI accepts is
    one the CLI will too - errors surface before a subprocess is spawned.
    """
    if not yaml_text.strip():
        return None, "config is empty"
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_text)
    try:
        return load_config(f.name), None
    except Exception as e:  # yaml errors, validation ValueErrors, bad shapes - all reported, never crash
        return None, f"{type(e).__name__}: {e}"
    finally:
        Path(f.name).unlink(missing_ok=True)


def make_server(host: str, port: int, app: App) -> ThreadingHTTPServer:
    allowed = {f"{h}:{port}" for h in ("127.0.0.1", "localhost", "[::1]", host)}
    handler = type("BoundHandler", (Handler,), {"app": app, "allowed_hosts": allowed})
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="IDS2Eval dashboard (local web UI)")
    parser.add_argument("--output", action="append", default=[],
                        help="An output.dir whose runs to list (repeatable; default ./output)")
    parser.add_argument("--config", help="A YAML config to prefill the New run editor with")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default 127.0.0.1 - keep it local)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab")
    args = parser.parse_args(argv)

    starter = _STARTER_CONFIG
    output_dirs = [Path(p) for p in args.output]
    if args.config:
        starter = Path(args.config).read_text()
        cfg, err = _validate(starter)
        if cfg:
            output_dirs.append(Path(cfg["output"]["dir"]))
        else:
            logger.warning("--config doesn't validate yet (%s); prefilling it anyway", err)
    if not output_dirs:
        output_dirs = [Path("./output")]

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning("Binding to %s: anyone who can reach this port can run configs on this machine", args.host)

    app = App(output_dirs, starter)
    server = make_server(args.host, args.port, app)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '::1') else args.host}:{args.port}/"
    logger.info("IDS2Eval dashboard at %s (listing runs in: %s)", url, ", ".join(map(str, app.output_dirs)))
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
