"use strict";
const $ = (s) => document.querySelector(s);
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) n.append(k);
  return n;
}
const VERDICT = {passed: "passed", passed_with_warnings: "passed with warnings", failed: "audit failed"};
function badge(kind, text) { return el("span", {class: "badge b-" + (kind || "none"), text}); }
function when(name) {  // run dirs are named YYYY-MM-DD_HHMMSS_micro (UTC)
  const m = /^(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})(\d{2})/.exec(name);
  return m ? `${m[1]} ${m[2]}:${m[3]}:${m[4]} UTC` : name;
}
async function api(path, body) {
  const opts = body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify(body)};
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

let runs = [], selected = null, view = "run", tab = "scorecard", pollTimer = null, editorText = null;
const store = {get(k) { try { return localStorage.getItem(k); } catch { return null; } },
               set(k, v) { try { localStorage.setItem(k, v); } catch {} }};
tab = store.get("ids2eval.tab") || "scorecard";

async function loadRuns(selectNewest) {
  try { runs = await api("/api/runs"); } catch (e) { runs = []; }
  if (selectNewest && runs.length) selected = runs[0].id;
  if (!selected && runs.length) selected = runs[0].id;
  renderRuns();
  if (view === "run") renderRun();
}

function renderRuns() {
  const box = $("#runs"); box.replaceChildren();
  if (!runs.length) {
    box.append(el("div", {class: "empty"}, "No runs yet. Start one with ", el("b", {text: "New run"}), "."));
    return;
  }
  for (const r of runs) {
    const kind = r.verdict || (r.run_status === "failed" ? "failed" : r.run_status === "running" ? "running" : null);
    const label = r.verdict ? VERDICT[r.verdict] : r.run_status === "failed" ? "run crashed"
                : r.run_status === "running" ? "running" : "no audit";
    box.append(el("button", {class: "run" + (view === "run" && r.id === selected ? " sel" : ""),
      onclick: () => { selected = r.id; view = "run"; renderRuns(); renderRun(); }},
      el("div", {class: "top"}, el("span", {class: "ds", text: r.dataset || "(unnamed)"}), badge(kind, label)),
      el("div", {class: "when", text: when(r.name)})));
  }
}

async function renderRun() {
  const main = $("#main");
  if (!selected) { main.replaceChildren(el("div", {class: "pane"}, el("p", {class: "hint",
    text: "Pick a run on the left, or start a new one."}))); return; }
  let d;
  try { d = await api("/api/run/" + selected); }
  catch (e) { main.replaceChildren(el("div", {class: "pane"}, el("div", {class: "error-box", text: e.message}))); return; }
  const base = "/files/" + selected + "/";
  const pane = el("div", {class: "pane"});
  pane.append(el("div", {class: "head"}, el("h2", {text: d.dataset || "(unnamed)"}),
    d.verdict ? badge(d.verdict, VERDICT[d.verdict]) : null,
    el("span", {class: "muted mono", text: d.name}), el("span", {class: "muted", text: d.output_dir})));
  if (d.run_status === "failed")
    pane.append(el("div", {class: "error-box", text: `Run crashed at stage "${d.failed_stage}": ${d.error}`}));

  const tabs = [["scorecard", "Scorecard"], ["benchmark", `Benchmark (${d.benchmark.length})`], ["files", "Files"]];
  pane.append(el("div", {class: "tabs"}, ...tabs.map(([k, t]) => el("button", {class: tab === k ? "on" : "", text: t,
    onclick: () => { tab = k; store.set("ids2eval.tab", k); renderRun(); }}))));

  if (tab === "scorecard") {
    if (d.files.includes("SCORECARD.html")) pane.append(el("iframe", {src: base + "SCORECARD.html",
      title: "Scorecard"}));
    else if (d.scorecard) pane.append(el("p", {class: "hint",
      text: "This run predates the HTML scorecard - open SCORECARD.md or scorecard.json under Files."}));
    else pane.append(el("p", {class: "hint", text: "No scorecard: the audit was skipped or the run didn't get that far."}));
  } else if (tab === "benchmark") {
    if (!d.benchmark.length) pane.append(el("p", {class: "hint", text: "No benchmark results in this run."}));
    else {
      const rows = [...d.benchmark].sort((a, b) => (+b.f1_weighted || 0) - (+a.f1_weighted || 0));
      const cols = ["stage", "classifier", "scaling", "sampling", "accuracy", "f1_weighted", "auc", "train_time_s",
                    "infer_time_s"];
      const num = new Set(["accuracy", "f1_weighted", "auc", "train_time_s", "infer_time_s"]);
      const fmt = (c, v) => v === "" || v == null ? "n/a" : num.has(c) ? (+v).toFixed(c.endsWith("_s") ? 2 : 4) : v;
      const note = "Sorted by weighted F1. Full per-class detail is in benchmark_details.json.";
      pane.append(el("p", {class: "hint", text: note}),
        el("div", {class: "tablewrap"}, el("table", {},
        el("thead", {}, el("tr", {}, ...cols.map(c => el("th", {text: c})))),
        el("tbody", {}, ...rows.map(r => el("tr", {}, ...cols.map(c =>
          el("td", {class: num.has(c) ? "num" : "", text: fmt(c, r[c])}))))))));
    }
  } else {
    pane.append(el("div", {class: "files"}, ...d.files.map(f => el("a", {href: base + encodeURIComponent(f),
      target: "_blank", rel: "noopener", class: "mono", text: f}))));
  }
  $("#main").replaceChildren(pane);
}

async function renderNewRun() {
  view = "new"; renderRuns();
  if (editorText === null) editorText = (await api("/api/starter-config")).yaml;
  const ta = el("textarea", {spellcheck: "false", "aria-label": "Config YAML"});
  ta.value = editorText; ta.addEventListener("input", () => { editorText = ta.value; });
  const skipAudit = el("input", {type: "checkbox", id: "sa"}), skipBench = el("input", {type: "checkbox", id: "sb"});
  const msg = el("span", {class: "msg"});
  const runBtn = el("button", {class: "primary", text: "Run"}), stopBtn = el("button", {text: "Stop"});
  const valBtn = el("button", {text: "Validate"});
  const log = el("pre", {class: "log mono", text: "No run started from this page yet."});
  const setMsg = (t, cls) => { msg.textContent = t; msg.className = "msg " + (cls || ""); };

  valBtn.onclick = async () => {
    try { const r = await api("/api/validate", {yaml: ta.value});
          r.ok ? setMsg(`Valid. Runs will be written under ${r.output_dir}/runs/`, "ok") : setMsg(r.error, "err"); }
    catch (e) { setMsg(e.message, "err"); }
  };
  runBtn.onclick = async () => {
    try { await api("/api/run", {yaml: ta.value, skip_audit: skipAudit.checked, skip_benchmark: skipBench.checked});
          setMsg("Running…"); poll(); }
    catch (e) { setMsg(e.message, "err"); }
  };
  stopBtn.onclick = () => api("/api/job/stop", {}).catch(e => setMsg(e.message, "err"));

  function show(job) {
    log.textContent = job.log.length ? job.log.join("\n") : log.textContent;
    log.scrollTop = log.scrollHeight;
    runBtn.disabled = job.state === "running"; stopBtn.disabled = job.state !== "running";
    if (job.state === "completed") {
      setMsg("Run completed. ", "ok");
      msg.append(el("button", {text: "Open its scorecard", onclick: () => { view = "run"; tab = "scorecard";
        loadRuns(true); }}));
    }
    if (job.state === "failed") setMsg(`Run failed (exit ${job.returncode}) - see the log.`, "err");
  }
  async function poll() {
    clearTimeout(pollTimer);
    let job; try { job = await api("/api/job"); } catch { return; }
    if (view !== "new") return;
    show(job);
    if (job.state === "running") pollTimer = setTimeout(poll, 1000);
    else if (job.state !== "idle") loadRuns(false);
  }

  $("#main").replaceChildren(el("div", {class: "pane"},
    el("div", {class: "head"}, el("h2", {text: "New run"}),
      el("span", {class: "muted", text: "Relative paths resolve against the directory the UI was started in."})),
    ta,
    el("div", {class: "row"}, el("label", {}, skipAudit, " skip audit"), el("label", {}, skipBench, " skip benchmark"),
      valBtn, runBtn, stopBtn, msg),
    log));
  poll();
}

$("#newrun").onclick = renderNewRun;
$("#refresh").onclick = () => loadRuns(false);
loadRuns(false);
