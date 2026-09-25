# IDS2Eval dashboard

A local web UI for browsing runs, reading their scorecards, and launching new
runs. Standard library only (`http.server`) - no extra dependencies.

```bash
ids2eval-dashboard --config my_config.yaml      # opens http://localhost:8765
python -m ids2eval.dashboard --output ./output  # same thing, without the console script
```

(`ids2eval-ui` is an older name for the same command, kept as an alias.)

## Layout

| File | What it is |
|---|---|
| `server.py` | The HTTP server: the JSON API, file serving, request guards, and the run job (one `python -m ids2eval` subprocess at a time) |
| `static/index.html` | The page skeleton |
| `static/style.css` | All styling, including dark mode (`prefers-color-scheme`) |
| `static/app.js` | All page behavior - fetches the API below and builds the DOM with `textContent` (never `innerHTML`) |

The static files are served as-is, so a change to them shows up on a browser
reload - no server restart. A change to `server.py` needs a restart.

## API

| Method | Path | Returns / does |
|---|---|---|
| GET | `/` , `/static/<file>` | The page and its assets (files directly in `static/` only) |
| GET | `/api/runs` | Every run under the listed output dirs, newest first, with verdict and status |
| GET | `/api/run/<dir_idx>/<run_name>` | One run: summary, `scorecard.json` content, benchmark rows |
| GET | `/files/<dir_idx>/<run_name>/<file>` | One artifact from a run directory (top level only) |
| GET | `/api/job` | The current/last launched run: state, exit code, last 2,000 log lines |
| GET | `/api/starter-config` | The YAML the New run editor starts with |
| POST | `/api/validate` | `{yaml}` → runs the CLI's own `load_config()` validation |
| POST | `/api/run` | `{yaml, skip_audit, skip_benchmark}` → starts a run (409 if one is already running) |
| POST | `/api/job/stop` | Terminates the running run |

## Security model

Local by design. It binds to `127.0.0.1`; every request must carry a localhost
`Host` header (blocks DNS rebinding); every POST must be `application/json` with no
foreign `Origin` (blocks other websites from launching runs); file serving is
limited to the top level of a known run directory; the page runs under a strict
Content-Security-Policy with no inline scripts. Anyone who can reach the port can
run a config - and a config can point at any file the server's user can read - so
don't bind it to a public interface.

## Troubleshooting

- **Blank page or unstyled page**: open the browser dev tools console. A CSP error
  means something inline was added to `index.html` - move it into `app.js` /
  `style.css`. A 404 on `/static/...` from a pip (non-editable) install means the
  static files weren't packaged - check `[tool.setuptools.package-data]` in
  `pyproject.toml`.
- **403 "bad Host header"**: you're reaching it through a hostname other than
  `localhost` / `127.0.0.1` (e.g. a reverse proxy). Forward the port instead
  (`ssh -L 8765:localhost:8765 host`), or start it with `--host` set to that name.
- **A run doesn't appear in the list**: runs are listed from the `--output` dirs and
  from any config launched in this session. Relative `output.dir` paths resolve
  against the directory the dashboard was started in.
- **Run fails immediately**: the full log is in the New run panel (`/api/job`);
  the same error is in that run's `run_status.json`.
- **Debug logging**: request logs go to the `ids2eval.dashboard.server` logger at
  DEBUG level.
