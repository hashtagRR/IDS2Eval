"use strict";
// IDS2Eval dashboard - a hash-routed single page over the JSON API in server.py.
// DOM is built with el() and textContent only (never innerHTML), and
// dynamic sizes go through element.style (CSSOM), which the page's CSP allows.

const $ = (s) => document.querySelector(s);
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  setAttrs(n, attrs);
  for (const k of kids.flat()) if (k != null && k !== false) n.append(k);
  return n;
}
function setAttrs(n, attrs) {
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.setAttribute("class", v);
    else if (k === "text") n.textContent = v;
    else if (k === "style") Object.assign(n.style, v);
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
}
async function api(path, body) {
  const opts = body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify(body)};
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
const store = {get(k) { try { return localStorage.getItem(k); } catch { return null; } },
               set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} }};

// ---------- vocabulary ----------

const STATUS = {ok: {label: "OK", icon: "✓"}, warning: {label: "Warning", icon: "!"}, flag: {label: "Flag", icon: "✕"}};
const VERDICT = {passed: {label: "Passed", status: "ok"},
                 passed_with_warnings: {label: "Passed with warnings", status: "warning"},
                 failed: {label: "Audit failed", status: "flag"}};
const RANK = {ok: 0, warning: 1, flag: 2};
// Display grouping only - the audit itself has no families. A check missing
// here (a new one) lands in "Other" rather than disappearing.
const FAMILIES = [
  ["Data integrity", ["data_integrity_check", "schema_fingerprint_check", "low_cardinality_warning",
                      "class_distribution_report"]],
  ["Duplicates & labels", ["dedup_check", "label_conflict_check", "near_duplicate_class_check"]],
  ["Shortcut features", ["leakage_screen", "one_rule_check", "feature_auc_ranking_check", "identity_column_flag",
                         "port_protocol_shortcut_check"]],
  ["Split & ordering leakage", ["temporal_leakage_check", "temporal_realism_check", "flow_group_leakage_check",
                                "row_order_leakage_check", "homogeneity_test"]],
  ["Falsification experiments", ["resplit_falsification", "scenario_holdout_falsification",
                                 "repeated_seed_falsification_check", "result_robustness_check"]],
  ["Known issues", ["known_issue_lookup"]],
];
const FAMILY_OF = Object.fromEntries(FAMILIES.flatMap(([f, cs]) => cs.map(c => [c, f])));
const familyOf = (check) => FAMILY_OF[check] || "Other";
const prettyCheck = (c) => c.replace(/_check$/, "").replace(/_/g, " ").replace(/\bauc\b/g, "AUC")
  .replace(/^./, m => m.toUpperCase());

const fmtInt = (n) => n == null || n === "" ? "n/a" : Number(n).toLocaleString();
function fmtNum(v) {
  if (typeof v !== "number") return String(v);
  if (Number.isInteger(v)) return v.toLocaleString();
  return Math.abs(v) < 1 ? v.toFixed(4) : v.toLocaleString(undefined, {maximumFractionDigits: 3});
}
function when(name) {  // run dirs are named YYYY-MM-DD_HHMMSS_micro (UTC)
  const m = /^(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})/.exec(name || "");
  return m ? `${m[1]} ${m[2]}:${m[3]} UTC` : name;
}
const runHref = (id, tab, extra) => "#/run/" + id.split("/").map(encodeURIComponent).join("/") +
  (tab ? "/" + tab : "") + (extra ? "/" + encodeURIComponent(extra) : "");

function statusBadge(status, text) {
  const s = STATUS[status];
  return el("span", {class: "badge s-" + (s ? status : "none")},
    s ? el("span", {class: "ic", "aria-hidden": "true", text: s.icon}) : null, text || (s ? s.label : "n/a"));
}
function dot(status) {
  const s = STATUS[status];
  return el("span", {class: "dot s-" + (s ? status : "none"), "aria-hidden": "true", text: s ? s.icon : "–"});
}
function runBadge(r) {
  if (r.verdict && VERDICT[r.verdict]) return statusBadge(VERDICT[r.verdict].status, VERDICT[r.verdict].label);
  if (r.run_status === "failed") return statusBadge("flag", "Run crashed");
  if (r.run_status === "running") return el("span", {class: "badge s-running", text: "Running"});
  return el("span", {class: "badge s-none", text: "No audit"});
}
function counts(c) {
  if (!c) return el("span", {class: "hint", text: "n/a"});
  return el("span", {class: "counts", title: `${c.flag || 0} flagged, ${c.warning || 0} warnings, ${c.ok || 0} ok`},
    el("span", {class: "c-flag", text: `✕ ${c.flag || 0}`}), el("span", {class: "c-warning", text: `! ${c.warning || 0}`}),
    el("span", {class: "c-ok", text: `✓ ${c.ok || 0}`}));
}
const kpi = (label, value, status, note) => el("div", {class: "kpi" + (status ? " s-" + status : "")},
  label, el("b", {text: value}), note ? el("div", {class: "kpi-note", text: note}) : null);
const card = (title, actions, ...kids) => el("section", {class: "card"},
  title || actions ? el("div", {class: "card-head"}, title ? el("h2", {text: title}) : el("span"), actions) : null,
  ...kids);
const pageHead = (title, sub, ...actions) => el("div", {class: "page-head"},
  el("div", {}, el("div", {class: "title"}, ...(typeof title === "string" ? [el("h1", {text: title})] : title)), sub ? el("div", {class: "sub"}, sub) : null),
  actions.length ? el("div", {class: "row"}, ...actions) : null);
const errorBox = (msg) => el("div", {class: "error-box", text: msg});
const empty = (...kids) => el("div", {class: "empty"}, ...kids);

// A sortable table: cols = [{key, label, num, render(row), sort(row)}].
function dataTable(cols, rows, {onRow, initial} = {}) {
  let sortKey = initial ? initial[0] : null, dir = initial ? initial[1] : -1;
  const tbody = el("tbody");
  const ths = cols.map(c => el("th", {class: (c.num ? "num " : "") + (c.nosort ? "" : "sortable"), scope: "col",
    "aria-sort": "none", text: c.label, onclick: c.nosort ? null : () => {
      dir = sortKey === c.key ? -dir : (c.num ? -1 : 1); sortKey = c.key; draw(); }}));
  function draw() {
    const col = cols.find(c => c.key === sortKey);
    const val = col ? (col.sort || (r => r[col.key])) : null;
    const sorted = col ? [...rows].sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null || x === "") return 1; if (y == null || y === "") return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * dir;
    }) : rows;
    ths.forEach((th, i) => {
      const on = cols[i].key === sortKey;
      th.setAttribute("aria-sort", on ? (dir > 0 ? "ascending" : "descending") : "none");
      th.textContent = cols[i].label + (on ? (dir > 0 ? " ▲" : " ▼") : "");
    });
    tbody.replaceChildren(...sorted.map(r => el("tr", {class: onRow ? "click" : null,
      onclick: onRow ? () => onRow(r) : null},
      ...cols.map(c => el("td", {class: c.num ? "num" : null}, c.render ? c.render(r) : fmtCell(r[c.key]))))));
  }
  draw();
  return el("div", {class: "tablewrap"}, el("table", {}, el("thead", {}, el("tr", {}, ...ths)), tbody));
}
const fmtCell = (v) => v == null || v === "" ? "n/a" : typeof v === "number" ? fmtNum(v) : String(v);

// ---------- tooltip ----------

const tipEl = $("#tip");
function showTip(evt, title, lines) {
  tipEl.replaceChildren(el("b", {text: title}), ...lines.map(l => el("div", {text: l})));
  tipEl.hidden = false;
  const r = evt.clientX != null && evt.type.startsWith("mouse") ? {x: evt.clientX, y: evt.clientY}
    : (() => { const b = evt.target.getBoundingClientRect(); return {x: b.right, y: b.top}; })();
  const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  tipEl.style.left = Math.min(r.x + 14, innerWidth - w - 8) + "px";
  tipEl.style.top = Math.max(8, Math.min(r.y + 14, innerHeight - h - 8)) + "px";
}
const hideTip = () => { tipEl.hidden = true; };
function withTip(node, title, lines) {
  node.setAttribute("tabindex", "0");
  node.setAttribute("aria-label", title + ": " + lines.join(", "));
  for (const ev of ["mouseenter", "mousemove", "focus"]) node.addEventListener(ev, e => showTip(e, title, lines));
  for (const ev of ["mouseleave", "blur"]) node.addEventListener(ev, hideTip);
  return node;
}

// ---------- data ----------

let runs = null, checkInfo = {}, detailCache = new Map(), pollTimer = null;
const editor = {text: null};

async function loadRuns() {
  try { runs = await api("/api/runs"); } catch { runs = []; }
  detailCache.clear();
  return runs;
}
async function runDetail(id) {
  if (!detailCache.has(id)) detailCache.set(id, api("/api/run/" + id));
  try { return await detailCache.get(id); } catch (e) { detailCache.delete(id); throw e; }
}
// Newest audited run per dataset name (runs arrive newest first).
function latestByDataset() {
  const seen = new Map();
  for (const r of runs) if (r.verdict && !seen.has(r.dataset)) seen.set(r.dataset, r);
  return [...seen.values()];
}

// ---------- router ----------

function parseHash() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  return {page: parts[0] || "dashboard", parts};
}
function setCrumbs(...items) {
  $("#crumbs").replaceChildren(...items.flatMap((it, i) => {
    const last = i === items.length - 1;
    const node = last || !it[1] ? el("span", {class: last ? "cur" : null, text: it[0]}) : el("a", {href: it[1], text: it[0]});
    return i ? [el("span", {"aria-hidden": "true", text: "›"}), node] : [node];
  }));
}
async function route() {
  clearTimeout(pollTimer); hideTip();
  $("#sidebar").classList.remove("open");
  const {page, parts} = parseHash();
  const nav = {dashboard: "dashboard", datasets: "datasets", runs: "runs", run: "runs", compare: "compare"}[page];
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("active", a.dataset.nav === nav));
  const main = $("#main");
  main.replaceChildren(el("div", {class: "loading", text: "Loading…"}));
  if (runs === null) await loadRuns();
  try {
    if (page === "dashboard") renderDashboard(main);
    else if (page === "datasets") renderDatasets(main);
    else if (page === "runs") renderRuns(main);
    else if (page === "run" && parts.length >= 3)
      await renderRun(main, parts[1] + "/" + parts[2], parts[3] || "overview", parts[4]);
    else if (page === "new") await renderNewRun(main);
    else if (page === "compare") renderCompare(main);
    else { setCrumbs(["Not found"]); main.replaceChildren(empty("No such page. ", el("a", {href: "#/", text: "Dashboard"}))); }
  } catch (e) {
    main.replaceChildren(errorBox(e.message));
  }
  document.title = "IDS2Eval · " + ($("#crumbs .cur")?.textContent || "Dashboard");
}

// ---------- dashboard ----------

function renderDashboard(main) {
  setCrumbs(["Dashboard"]);
  const latest = latestByDataset();
  const failing = latest.filter(r => r.verdict === "failed").length;
  const flags = latest.reduce((s, r) => s + ((r.counts || {}).flag || 0), 0);
  const warns = latest.reduce((s, r) => s + ((r.counts || {}).warning || 0), 0);
  const kids = [
    pageHead("Dashboard", "Audit runs found in the output directories this dashboard was started with.",
      el("a", {class: "btn primary", href: "#/new", text: "+ New run"})),
    el("div", {class: "kpis"},
      kpi("Datasets audited", String(latest.length)),
      kpi("Runs", String(runs.length)),
      kpi("Failing audits", `${failing} / ${latest.length}`, failing ? "flag" : "ok", "latest run per dataset"),
      kpi("Flagged checks", String(flags), flags ? "flag" : "ok", "across latest runs"),
      kpi("Warnings", String(warns), warns ? "warning" : "ok", "across latest runs")),
  ];
  if (!runs.length) {
    kids.push(card(null, null, empty("No runs yet. ", el("a", {class: "btn primary", href: "#/new", text: "Start a run"}))));
    main.replaceChildren(...kids); return;
  }
  const recent = runs.slice(0, 8);
  kids.push(el("div", {class: "grid g2-wide"},
    card("Where audits fail", el("a", {class: "btn", href: "#/datasets", text: "Audit matrix →"}),
      el("p", {class: "hint", text: `Status of each check across the latest run of ${latest.length} dataset` +
        (latest.length === 1 ? "" : "s") + ", most-flagged first."}),
      checkStatusChart(latest)),
    card("Recent runs", el("a", {class: "btn", href: "#/runs", text: "All runs →"}),
      dataTable([
        {key: "dataset", label: "Dataset", render: r => el("b", {text: r.dataset || "(unnamed)"})},
        {key: "verdict", label: "Verdict", nosort: true, render: runBadge},
        {key: "counts", label: "Checks", nosort: true, render: r => counts(r.counts)},
        {key: "name", label: "When", render: r => el("span", {class: "hint", text: when(r.name)})},
      ], recent, {onRow: r => { location.hash = runHref(r.id); }}))));
  main.replaceChildren(...kids);
}

// Horizontal 100%-stacked bars: one per check, flag | warning | ok segments.
// Plain HTML rows rather than SVG, so labels stay at text size at any width.
function checkStatusChart(latest) {
  const tally = new Map();
  for (const r of latest) for (const [c, s] of Object.entries(r.check_status || {})) {
    if (!tally.has(c)) tally.set(c, {ok: 0, warning: 0, flag: 0});
    if (s in RANK) tally.get(c)[s]++;
  }
  const rows = [...tally].sort((a, b) => b[1].flag - a[1].flag || b[1].warning - a[1].warning || a[0].localeCompare(b[0]));
  if (!rows.length) return empty("No audited runs yet.");
  const chart = el("div", {class: "hbars", role: "list", "aria-label": "Check status across datasets"},
    ...rows.map(([check, t]) => {
      const total = t.ok + t.warning + t.flag || 1;
      return withTip(el("div", {class: "hb-row", role: "listitem"},
        el("span", {class: "hb-label", text: prettyCheck(check)}),
        el("div", {class: "hb-track"}, ...["flag", "warning", "ok"].filter(s => t[s]).map(s =>
          el("span", {class: "hb-seg s-" + s, style: {flexGrow: String(t[s] / total), flexBasis: "0"}}))),
        el("span", {class: "hb-val", text: t.flag ? `${t.flag} ✕` : ""})),
        prettyCheck(check), [`${t.flag} flagged`, `${t.warning} warning`, `${t.ok} ok`, `of ${t.ok + t.warning + t.flag} datasets`]);
    }));
  const table = dataTable([
    {key: "check", label: "Check", render: r => prettyCheck(r.check)},
    {key: "flag", label: "Flag", num: true}, {key: "warning", label: "Warning", num: true}, {key: "ok", label: "OK", num: true},
  ], rows.map(([check, t]) => ({check, ...t})));
  return toggleView(el("div", {class: "legend"}, ...["flag", "warning", "ok"].map(s =>
    el("span", {}, el("i", {class: "sw s-" + s}), STATUS[s].label))), chart, table);
}

// Chart with a "Table" toggle, so no reading depends on color alone.
function toggleView(legend, chart, table) {
  const box = el("div", {}, chart);
  const btn = el("button", {class: "chip", text: "Table view", "aria-pressed": "false"});
  btn.onclick = () => {
    const on = btn.getAttribute("aria-pressed") !== "true";
    btn.setAttribute("aria-pressed", String(on)); btn.classList.toggle("on", on);
    btn.textContent = on ? "Chart view" : "Table view";
    box.replaceChildren(on ? table : chart);
  };
  return el("div", {class: "stack"}, el("div", {class: "row"}, legend, el("span", {class: "spacer"}), btn), box);
}

// ---------- datasets ----------

function renderDatasets(main) {
  setCrumbs(["Datasets"]);
  const latest = latestByDataset();
  const runCount = new Map();
  for (const r of runs) runCount.set(r.dataset, (runCount.get(r.dataset) || 0) + 1);
  const kids = [pageHead("Datasets", "One row per dataset, from its most recent audited run.")];
  if (!latest.length) { kids.push(card(null, null, empty("No audited runs yet."))); main.replaceChildren(...kids); return; }
  kids.push(card(null, null, dataTable([
    {key: "dataset", label: "Dataset", render: r => el("b", {text: r.dataset})},
    {key: "train_rows", label: "Train rows", num: true}, {key: "test_rows", label: "Test rows", num: true},
    {key: "feature_count", label: "Features", num: true},
    {key: "verdict", label: "Verdict", render: runBadge},
    {key: "flags", label: "Checks", sort: r => (r.counts || {}).flag || 0, render: r => counts(r.counts)},
    {key: "runs", label: "Runs", num: true, sort: r => runCount.get(r.dataset), render: r => fmtInt(runCount.get(r.dataset))},
    {key: "name", label: "Last run", render: r => el("span", {class: "hint", text: when(r.name)})},
  ], latest, {onRow: r => { location.hash = runHref(r.id); }})));
  kids.push(card("Audit matrix", null,
    el("p", {class: "hint", text: "Final status of every check (after deduplication, where it ran) for each " +
      "dataset's latest run. Select a cell for that check's evidence."}),
    auditMatrix(latest)));
  main.replaceChildren(...kids);
}

function auditMatrix(latest) {
  const checks = [...new Set(latest.flatMap(r => Object.keys(r.check_status || {})))];
  const order = (c) => { const f = FAMILIES.findIndex(([n]) => n === familyOf(c)); return f < 0 ? 99 : f; };
  checks.sort((a, b) => order(a) - order(b) || a.localeCompare(b));
  const rows = [];
  let fam = null;
  for (const c of checks) {
    if (familyOf(c) !== fam) {
      fam = familyOf(c);
      rows.push(el("tr", {}, el("th", {colspan: String(latest.length + 1), text: fam})));
    }
    rows.push(el("tr", {}, el("td", {class: "check", text: prettyCheck(c)}), ...latest.map(r => {
      const s = (r.check_status || {})[c];
      return el("td", {class: "cell"}, s ? el("a", {href: runHref(r.id, "checks", c),
        title: `${r.dataset} · ${prettyCheck(c)}: ${STATUS[s]?.label || s}`,
        "aria-label": `${r.dataset}, ${prettyCheck(c)}: ${STATUS[s]?.label || s}`}, dot(s)) : el("span", {class: "hint", text: "·"}));
    })));
  }
  return el("div", {class: "tablewrap"}, el("table", {class: "matrix"},
    el("thead", {}, el("tr", {}, el("th", {text: "Check"}), ...latest.map(r => el("th", {class: "ds", scope: "col"},
      el("a", {href: runHref(r.id), text: r.dataset}))))),
    el("tbody", {}, ...rows)));
}

// ---------- runs ----------

function renderRuns(main) {
  setCrumbs(["Runs"]);
  const filter = {q: store.get("ids2eval.runs.q") || "", v: "all"};
  const host = el("div");
  const search = el("input", {type: "search", placeholder: "Filter by dataset or run…", value: filter.q,
    "aria-label": "Filter runs", oninput: () => { filter.q = search.value; store.set("ids2eval.runs.q", search.value); draw(); }});
  const opts = [["all", "All"], ["failed", "Failed"], ["passed_with_warnings", "Warnings"], ["passed", "Passed"],
                ["crashed", "Crashed"]];
  const chipBox = el("div", {class: "chips"});
  function draw() {
    chipBox.replaceChildren(...opts.map(([k, t]) => el("button", {class: "chip" + (filter.v === k ? " on" : ""), text: t,
      "aria-pressed": String(filter.v === k), onclick: () => { filter.v = k; draw(); }})));
    const q = filter.q.toLowerCase();
    const shown = runs.filter(r => (!q || (r.dataset || "").toLowerCase().includes(q) || r.name.includes(q) ||
      r.output_dir.toLowerCase().includes(q)) &&
      (filter.v === "all" || (filter.v === "crashed" ? r.run_status === "failed" : r.verdict === filter.v)));
    host.replaceChildren(shown.length ? dataTable([
      {key: "name", label: "When", render: r => el("span", {class: "mono", text: when(r.name)})},
      {key: "dataset", label: "Dataset", render: r => el("b", {text: r.dataset || "(unnamed)"})},
      {key: "verdict", label: "Result", render: runBadge},
      {key: "flags", label: "Checks", sort: r => (r.counts || {}).flag, render: r => counts(r.counts)},
      {key: "output_dir", label: "Output dir", render: r => el("span", {class: "hint mono", text: r.output_dir})},
    ], shown, {onRow: r => { location.hash = runHref(r.id); }}) : empty("No runs match."));
  }
  draw();
  main.replaceChildren(pageHead("Runs", `${runs.length} run${runs.length === 1 ? "" : "s"}, newest first.`,
    el("a", {class: "btn primary", href: "#/new", text: "+ New run"})),
    card(null, null, el("div", {class: "row"}, search, chipBox), host));
}

// ---------- one run ----------

const RUN_TABS = [["overview", "Overview"], ["checks", "Checks"], ["recommendations", "Recommendations"],
                  ["benchmark", "Benchmark"], ["provenance", "Provenance"], ["scorecard", "Scorecard"], ["files", "Files"]];

async function renderRun(main, id, tab, sel) {
  const d = await runDetail(id);
  const sc = d.scorecard || {};
  setCrumbs(["Runs", "#/runs"], [d.dataset || "(unnamed)", null], [when(d.name)]);
  const base = "/files/" + id + "/";
  const citeHost = el("div");
  const actions = [];
  if (d.files.includes("scorecard.json")) {
    const citeBtn = el("button", {text: "Cite"});
    citeBtn.onclick = async () => {
      citeBtn.disabled = true;
      try {
        const r = await api("/api/run/" + id + "/citation");
        citeHost.replaceChildren(card("BibTeX", el("div", {class: "row"}, copyBtn(r.bibtex),
          el("button", {text: "Close", onclick: () => citeHost.replaceChildren()})), el("pre", {class: "code", text: r.bibtex})));
      } catch (e) { citeHost.replaceChildren(errorBox(e.message)); }
      finally { citeBtn.disabled = false; }
    };
    actions.push(citeBtn);
  }
  if (d.files.includes("SCORECARD.html")) actions.push(el("a", {class: "btn primary", href: base + "SCORECARD.html",
    target: "_blank", rel: "noopener", text: "Open scorecard ↗"}));

  const c = d.counts || {};
  const total = (c.ok || 0) + (c.warning || 0) + (c.flag || 0);
  const kids = [
    pageHead([el("h1", {text: d.dataset || "(unnamed)"}), runBadge(d)],
      [el("span", {class: "mono", text: d.name}), " · ", d.output_dir], ...actions),
    citeHost,
  ];
  if (d.run_status === "failed") kids.push(errorBox(`Run crashed at stage "${d.failed_stage}": ${d.error}`));
  if (d.counts) kids.push(el("div", {class: "kpis"},
    kpi("Checks", String(total)), kpi("OK", String(c.ok || 0), "ok"),
    kpi("Warnings", String(c.warning || 0), c.warning ? "warning" : null),
    kpi("Flags", String(c.flag || 0), c.flag ? "flag" : null),
    kpi("Train rows", fmtInt(d.train_rows)), kpi("Test rows", fmtInt(d.test_rows)), kpi("Features", fmtInt(d.feature_count))));
  kids.push(el("nav", {class: "tabs", "aria-label": "Run sections"}, ...RUN_TABS.map(([k, t]) =>
    el("a", {href: runHref(id, k), class: tab === k ? "on" : null, "aria-current": tab === k ? "page" : null,
      text: k === "benchmark" && d.benchmark.length ? `${t} (${d.benchmark.length})` : t}))));

  const body = el("div", {class: "grid"});
  kids.push(body);
  main.replaceChildren(...kids);
  if (tab === "overview") renderOverview(body, d, id);
  else if (tab === "checks") renderChecks(body, d, id, sel);
  else if (tab === "recommendations") await renderRecommendations(body, id);
  else if (tab === "benchmark") await renderBenchmark(body, d, id);
  else if (tab === "provenance") renderProvenance(body, d, sc);
  else if (tab === "scorecard") renderScorecardTab(body, d, base);
  else renderFiles(body, d, base);
}

function copyBtn(text) {
  const b = el("button", {text: "Copy"});
  b.onclick = async () => {
    try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; }
    catch { b.textContent = "Copy failed"; }
    setTimeout(() => { b.textContent = "Copy"; }, 1500);
  };
  return b;
}

function checksOf(d) {
  return ((d.scorecard || {}).checks || []).map(c => {
    const fin = c.after || c.before || {};
    return {check: c.check, category: c.category, status: fin.status, summary: fin.summary, evidence: fin.evidence,
            before: c.before, after: c.after};
  });
}

function renderOverview(body, d, id) {
  const checks = checksOf(d);
  if (!checks.length) {
    body.append(card(null, null, empty(d.run_status === "running" ? "This run is still in progress."
      : "No audit in this run (skipped, or it didn't get that far). See Benchmark or Files.")));
    return;
  }
  const sc = d.scorecard;
  // Families
  const fams = new Map();
  for (const c of checks) {
    const f = familyOf(c.check);
    if (!fams.has(f)) fams.set(f, []);
    fams.get(f).push(c);
  }
  const famOrder = [...FAMILIES.map(([f]) => f), "Other"].filter(f => fams.has(f));
  const famCard = card("Check families", null, ...famOrder.map(f => {
    const cs = fams.get(f), ok = cs.filter(c => c.status === "ok").length;
    const worst = cs.reduce((w, c) => RANK[c.status] > RANK[w] ? c.status : w, "ok");
    return el("div", {class: "fam"},
      el("div", {class: "lbl"}, el("span", {}, el("b", {text: f}), el("span", {class: "hint", text: ` · ${ok}/${cs.length} ok`})),
        statusBadge(worst)),
      el("div", {class: "progress s-" + worst, role: "img", "aria-label": `${ok} of ${cs.length} ok`},
        el("span", {style: {width: (100 * ok / cs.length) + "%"}})));
  }));
  // Top findings
  const bad = checks.filter(c => c.status !== "ok").sort((a, b) => RANK[b.status] - RANK[a.status]);
  const findCard = card("Findings", el("a", {class: "btn", href: runHref(id, "recommendations"), text: "Recommendations →"}),
    bad.length ? el("div", {}, ...bad.map(c => el("div", {class: "finding"}, dot(c.status),
      el("a", {href: runHref(id, "checks", c.check), text: prettyCheck(c.check)}), el("p", {text: c.summary || ""}))))
      : empty("Every check came back ok."));
  body.append(el("div", {class: "grid g2"}, findCard, famCard));
  const visuals = visualSummary(d, id, checks);
  if (visuals.length) body.append(el("h2", {class: "section-title", text: "Evidence at a glance"}),
    el("div", {class: "grid g2"}, ...visuals));

  const extra = [];
  const de = sc.dedup_effect;
  if (de) {
    const changed = checks.filter(c => c.before && c.after && c.before.status !== c.after.status);
    extra.push(card("Effect of deduplication", null,
      dedupComposition(de),
      el("dl", {class: "kv"},
        el("dt", {text: "Train duplicates dropped"}), el("dd", {text: fmtInt(de.train_duplicates_dropped)}),
        el("dt", {text: "Test rows leaking a train match"}), el("dd", {text: fmtInt(de.test_leakage_dropped)}),
        el("dt", {text: "Test-internal duplicates"}), el("dd", {text: fmtInt(de.test_duplicates_dropped)})),
      changed.length ? el("div", {}, el("h3", {text: "Checks that changed after deduplication"}),
        ...changed.map(c => el("div", {class: "row"}, el("a", {href: runHref(id, "checks", c.check), text: prettyCheck(c.check)}),
          statusBadge(c.before.status), "→", statusBadge(c.after.status))))
        : el("p", {class: "hint", text: "No check changed status after deduplication."})));
  }
  const prev = sc.previous_run_comparison;
  if (prev) extra.push(prevRunCard(prev, d));
  if (extra.length) body.append(el("div", {class: "grid g2"}, ...extra));
}

// The checks whose evidence charts best, in reading order; each card shows
// only when that check recorded data in this run.
const OVERVIEW_VIZ = [
  ["class_distribution_report", "Class distribution"],
  ["dedup_check", "Duplicates and train/test leakage by class", (d, b) => dedupByClass(b && b.by_class ? b : d)],
  ["feature_auc_ranking_check", "Strongest single features"],
  ["identity_column_flag", "Identity-like columns"],
  ["homogeneity_test", "Test-to-train nearest neighbours"],
  ["one_rule_check", "One-rule baseline"],
  ["result_robustness_check", "Accuracy under each condition"],
  ["repeated_seed_falsification_check", "Falsification across seeds"],
  ["label_conflict_check", "Conflicting labels"],
];
function reportsByCheck(d) {
  const by = (rep) => Object.fromEntries((rep || []).map(r => [r.check, r.details || {}]));
  return [by(d.audit_report), by(d.audit_report_before)];
}
function visualSummary(d, id, checks) {
  const [after, before] = reportsByCheck(d);
  const status = Object.fromEntries(checks.map(c => [c.check, c.status]));
  const cards = [];
  for (const [check, title, pick] of OVERVIEW_VIZ) {
    const nodes = pick ? [pick(after[check] || {}, before[check])].filter(Boolean) : checkViz(check, after[check], before[check]);
    if (!nodes.length) continue;
    cards.push(card(title, el("div", {class: "row"}, status[check] ? statusBadge(status[check]) : null,
      el("a", {class: "btn", href: runHref(id, "checks", check), text: "Details →"})), ...nodes));
  }
  return cards;
}

function prevRunCard(prev, d) {
  const prevRun = runs.find(r => r.name === prev.previous_run && r.output_dir === d.output_dir);
  return card("Compared with the previous run", prevRun ? el("a", {class: "btn", href: runHref(prevRun.id),
    text: "Open it →"}) : null,
    el("dl", {class: "kv"},
      el("dt", {text: "Previous run"}), el("dd", {class: "mono", text: prev.previous_run}),
      el("dt", {text: "Its verdict"}), el("dd", {}, prev.previous_verdict && VERDICT[prev.previous_verdict]
        ? statusBadge(VERDICT[prev.previous_verdict].status, VERDICT[prev.previous_verdict].label) : "n/a"),
      el("dt", {text: "Data fingerprint"}), el("dd", {}, prev.fingerprint_changed
        ? statusBadge("warning", "Changed") : statusBadge("ok", "Unchanged")),
      el("dt", {text: "Checks that changed"}), el("dd", {}, (prev.changed_checks || []).length
        ? el("div", {}, ...prev.changed_checks.map(cc => el("div", {text: typeof cc === "string" ? cc : JSON.stringify(cc)})))
        : "none")));
}

function renderChecks(body, d, id, sel) {
  const checks = checksOf(d);
  if (!checks.length) { body.append(card(null, null, empty("No audit in this run."))); return; }
  const details = Object.fromEntries((d.audit_report || []).map(r => [r.check, r]));
  const bad = checks.filter(c => c.status !== "ok").sort((a, b) => RANK[b.status] - RANK[a.status]);
  const current = checks.find(c => c.check === sel) || bad[0] || checks[0];
  let filter = store.get("ids2eval.checkFilter") || "all";

  const list = el("nav", {class: "card checklist", "aria-label": "Checks"});
  function drawList() {
    const chips = el("div", {class: "chips"}, ...[["all", "All"], ["flag", "Flag"], ["warning", "Warning"], ["ok", "OK"]].map(
      ([k, t]) => el("button", {class: "chip" + (filter === k ? " on" : ""), "aria-pressed": String(filter === k),
        text: `${t} ${k === "all" ? checks.length : checks.filter(c => c.status === k).length}`,
        onclick: () => { filter = k; store.set("ids2eval.checkFilter", k); drawList(); }})));
    const items = [chips];
    for (const f of [...FAMILIES.map(([n]) => n), "Other"]) {
      const cs = checks.filter(c => familyOf(c.check) === f && (filter === "all" || c.status === filter));
      if (!cs.length) continue;
      items.push(el("div", {class: "grp", text: f}));
      for (const c of cs) items.push(el("a", {href: runHref(id, "checks", c.check),
        class: c.check === current.check ? "sel" : null, "aria-current": c.check === current.check ? "true" : null},
        dot(c.status), prettyCheck(c.check)));
    }
    list.replaceChildren(...items);
  }
  drawList();

  const c = current, info = checkInfo[c.check], rep = details[c.check];
  const viz = checkViz(c.check, rep?.details, reportsByCheck(d)[1][c.check]);
  const generic = rep && rep.details && Object.keys(rep.details).length ? renderValue(rep.details, 0) : null;
  const changed = c.before && c.after && c.before.status !== c.after.status;
  const detail = card(null, null,
    el("div", {class: "card-head"}, el("div", {class: "title row"}, el("h1", {text: prettyCheck(c.check)}), statusBadge(c.status)),
      el("span", {class: "mono hint", text: c.check})),
    el("div", {class: "row"}, el("span", {class: "tag", text: familyOf(c.check)}),
      c.evidence ? el("span", {class: "tag", text: "evidence: " + c.evidence}) : null,
      c.category ? el("span", {class: "tag", text: "category: " + c.category}) : null,
      changed ? el("span", {class: "row"}, "Before dedup:", statusBadge(c.before.status), "→", statusBadge(c.after.status)) : null),
    el("p", {class: "summary", text: c.summary || "No summary recorded."}),
    info ? el("div", {class: "explain"}, el("div", {}, el("b", {text: "What it checks"}), info.what),
      el("div", {}, el("b", {text: "Rule"}), info.rule)) : null,
    changed && c.before.summary ? el("div", {}, el("h3", {text: "Before deduplication"}),
      el("p", {class: "hint", text: c.before.summary})) : null,
    el("h3", {text: "Evidence"}),
    viz.length ? el("div", {class: "stack"}, ...viz) : null,
    viz.length && generic ? el("details", {class: "raw"}, el("summary", {text: "All recorded values"}), generic)
      : generic || el("p", {class: "hint", text: "No structured details recorded for this check."}),
    rep ? el("details", {class: "raw"}, el("summary", {text: "Raw JSON"}),
      el("pre", {class: "code", text: JSON.stringify(rep, null, 2)})) : null);
  body.append(el("div", {class: "split"}, list, detail));
}

// Generic renderer for a check's `details` - shapes vary per check, so this
// picks a view by shape: number maps become bar lists, maps of flat records
// become tables, everything else a key/value list.
function renderValue(v, depth) {
  const isObj = (x) => x && typeof x === "object" && !Array.isArray(x);
  const scalar = (x) => x == null || ["string", "number", "boolean"].includes(typeof x);
  if (scalar(v)) return el("span", {class: typeof v === "number" ? "mono" : null, text: v == null ? "n/a" : fmtNum(v)});
  if (depth > 3) return el("pre", {class: "code", text: JSON.stringify(v, null, 2)});
  if (Array.isArray(v)) {
    if (!v.length) return el("span", {class: "hint", text: "none"});
    if (v.every(scalar)) return el("div", {class: "chips"}, ...v.slice(0, 60).map(x => el("span", {class: "tag", text: fmtNum(x)})),
      v.length > 60 ? el("span", {class: "hint", text: `+${v.length - 60} more`}) : null);
    if (v.every(x => isObj(x) && Object.values(x).every(scalar))) return recordTable(v.map((x, i) => [String(i + 1), x]));
    return el("pre", {class: "code", text: JSON.stringify(v, null, 2)});
  }
  const entries = Object.entries(v);
  if (!entries.length) return el("span", {class: "hint", text: "none"});
  if (entries.length > 1 && entries.every(([, x]) => typeof x === "number")) return barList(entries);
  if (entries.length > 1 && entries.every(([, x]) => isObj(x) && Object.values(x).every(scalar))) return recordTable(entries);
  return el("dl", {class: "kv"}, ...entries.flatMap(([k, x]) => [el("dt", {text: k.replace(/_/g, " ")}),
    el("dd", {}, renderValue(x, depth + 1))]));
}
function recordTable(entries) {
  let cols = [...new Set(entries.flatMap(([, x]) => Object.keys(x)))];
  if (cols.length > 2 * entries.length) {  // e.g. {counts: {15 classes}, shares: {...}} - one row per class reads better
    const flipped = cols.map(c => [c, Object.fromEntries(entries.map(([k, x]) => [k, x[c]]))]);
    entries = flipped; cols = [...new Set(entries.flatMap(([, x]) => Object.keys(x)))];
  }
  const rows = entries.slice(0, 200).map(([k, x]) => ({_key: k, ...x}));
  return el("div", {}, dataTable([{key: "_key", label: ""}, ...cols.map(c => ({key: c, label: c.replace(/_/g, " "),
    num: rows.some(r => typeof r[c] === "number"), render: r => fmtCell(typeof r[c] === "boolean" ? String(r[c]) : r[c])}))], rows),
    entries.length > 200 ? el("p", {class: "hint", text: `Showing 200 of ${entries.length}.`}) : null);
}
// Labelled bars from zero (never a truncated axis) with the exact value printed.
function barList(entries) {
  const shown = entries.slice(0, 25);
  const max = Math.max(...shown.map(([, x]) => Math.abs(x)), 1e-12);
  return el("div", {}, el("div", {class: "barlist"}, ...shown.flatMap(([k, x]) => [
    el("span", {class: "bl-label", title: k, text: k}),
    el("div", {class: "bl-track"}, el("div", {class: "bl-bar", style: {width: (100 * Math.abs(x) / max) + "%"}})),
    el("span", {class: "bl-val", text: fmtNum(x)})])),
    entries.length > 25 ? el("p", {class: "hint", text: `Showing 25 of ${entries.length}.`}) : null);
}

async function renderRecommendations(body, runId) {
  let recs;
  try { recs = (await api("/api/run/" + runId + "/recommendations")).recommendations; }
  catch (e) { body.append(errorBox(e.message)); return; }
  if (!recs.length) {
    body.append(card(null, null, empty("Nothing flagged or warned in this run has a recommendation.")));
    return;
  }
  const checkboxes = [];
  const cards = recs.map(r => {
    const cb = r.patch ? el("input", {type: "checkbox"}) : null;
    if (cb) { cb.checked = true; checkboxes.push([cb, r.id]); }
    const head = cb ? el("label", {class: "rec-head"}, cb, el("strong", {text: r.title}))
      : el("div", {class: "rec-head"}, el("strong", {text: r.title}), el("span", {class: "tag", text: "no config fix"}));
    const c = el("div", {class: "rec-card"}, head,
      el("div", {class: "row"}, ...r.checks.map(ch => el("a", {class: "tag", href: runHref(runId, "checks", ch),
        text: prettyCheck(ch)}))),
      el("p", {text: r.explanation}));
    if (r.patch) c.append(el("pre", {class: "code", text: JSON.stringify(r.patch, null, 2)}));
    return c;
  });
  const applyBtn = el("button", {class: "primary", text: "Apply selected → New run"});
  applyBtn.disabled = checkboxes.length === 0;
  const msg = el("span", {class: "msg"});
  applyBtn.onclick = async () => {
    applyBtn.disabled = true;
    const ids = checkboxes.filter(([cb]) => cb.checked).map(([, id]) => id);
    try {
      editor.text = (await api("/api/run/" + runId + "/apply-recommendations", {ids})).yaml;
      location.hash = "#/new";
    } catch (e) { msg.textContent = e.message; msg.className = "msg err"; applyBtn.disabled = false; }
  };
  body.append(card("Recommendations", checkboxes.length ? el("div", {class: "row"}, msg, applyBtn) : null,
    el("p", {class: "hint", text: "Only structural fixes get a checkbox - a shortcut-feature flag gets more " +
      "evidence to enable instead of an automatic drop, and a few checks report a property of the data with no " +
      "config fix at all; see each explanation."}), ...cards));
}

const METRICS = [["f1_macro", "Macro F1"], ["f1_weighted", "Weighted F1"], ["accuracy", "Accuracy"], ["auc", "AUC"],
                 ["train_time_s", "Train time (s)"], ["infer_time_s", "Inference time (s)"]];
async function renderBenchmark(body, d, id) {
  const rows = d.benchmark.map(r => {
    const o = {...r};
    for (const [k] of METRICS) o[k] = r[k] === "" || r[k] == null ? null : +r[k];
    return o;
  });
  if (!rows.length) { body.append(card(null, null, empty("No benchmark results in this run."))); return; }
  const metrics = METRICS.filter(([k]) => rows.some(r => r[k] != null));
  const scores = metrics.filter(([k]) => !k.endsWith("_s"));
  const stages = [...new Set(rows.map(r => r.stage))];
  let metric = metrics.some(([k]) => k === store.get("ids2eval.metric")) ? store.get("ids2eval.metric") : metrics[0][0];
  let stage = stages[0], picked = null;
  const label = Object.fromEntries(METRICS);
  // Only name the scaling/sampling variant when the run actually varied it.
  const multiVariant = new Set(rows.map(r => `${r.scaling}|${r.sampling}`)).size > 1;
  const nameOf = (r) => r.classifier + (multiVariant ? ` (${[r.scaling, r.sampling].filter(Boolean).join(", ")})` : "");
  const keyOf = (r) => [r.stage, r.scaling, r.sampling, r.classifier].join("|");

  const sel = el("select", {"aria-label": "Metric", onchange: () => { metric = sel.value; store.set("ids2eval.metric", metric); draw(); }},
    ...metrics.map(([k, t]) => el("option", {value: k, text: t})));
  sel.value = metric;
  const stageChips = el("div", {class: "chips"});
  const chartBox = el("div"), scatterBox = el("div"), perClassBox = el("div"), cmBox = el("div"), fiBox = el("div");
  const clfSel = el("select", {"aria-label": "Classifier", onchange: () => { picked = clfSel.value; drawDetail(); }});
  let details = null;

  const stageRows = () => rows.filter(r => r.stage === stage);
  function draw() {
    stageChips.replaceChildren(...(stages.length > 1 ? stages.map(s => el("button", {class: "chip" + (s === stage ? " on" : ""),
      text: s, "aria-pressed": String(s === stage), onclick: () => { stage = s; picked = null; draw(); }})) : []));
    const lower = metric.endsWith("_s");
    const pts = stageRows().filter(r => r[metric] != null).sort((a, b) => lower ? a[metric] - b[metric] : b[metric] - a[metric]);
    chartBox.replaceChildren(pts.length ? classifierChart(pts, metric, nameOf) : empty("No values for this metric."));
    const yKey = lower ? (scores[0] || [])[0] : metric;
    const sc = yKey && rows.some(r => r.train_time_s != null) ? scatter({
      points: stageRows().filter(r => r[yKey] != null && r.train_time_s > 0).map(r => ({x: r.train_time_s, y: r[yKey], label: nameOf(r),
        tip: r.infer_time_s != null ? [`Inference time: ${r.infer_time_s.toFixed(2)} s`] : []})),
      xLog: true, xLabel: "Training time (s, log scale)", yLabel: label[yKey], xFmt: v => v.toFixed(2) + " s",
      yFmt: v => v.toFixed(4), unitY: true}) : null;
    scatterBox.replaceChildren(sc || empty("Not enough timed results to plot."));
    if (details) drawDetail();
  }

  function drawDetail() {
    const sr = stageRows().filter(r => details[keyOf(r)]);
    if (!sr.length) { perClassBox.replaceChildren(empty("No per-class detail for this stage.")); cmBox.replaceChildren(); fiBox.replaceChildren(); return; }
    const byScore = [...sr].sort((a, b) => (b[scores[0]?.[0]] ?? 0) - (a[scores[0]?.[0]] ?? 0));
    // Per-class F1, classes ordered by test support (largest first)
    const reports = byScore.map(r => [nameOf(r), details[keyOf(r)].per_class_report || {}]);
    const support = {};
    for (const [, rep] of reports) for (const [c, v] of Object.entries(rep))
      if (v && typeof v === "object" && !/avg$/.test(c)) support[c] = Math.max(support[c] || 0, v.support || 0);
    const classes = Object.keys(support).sort((a, b) => support[b] - support[a]);
    const repOf = Object.fromEntries(reports);
    perClassBox.replaceChildren(heatmap({rows: reports.map(([n]) => n), cols: classes, rowHead: "Classifier",
      value: (r, c) => repOf[r][c]?.["f1-score"], text: v => v.toFixed(2), domain: [0, 1],
      caption: "columns ordered by test support, largest first",
      tip: (v, r, c) => { const x = repOf[r][c] || {}; return [`F1: ${v.toFixed(4)}`, `Precision: ${(x.precision ?? NaN).toFixed(4)}`,
        `Recall: ${(x.recall ?? NaN).toFixed(4)}`, `Support: ${fmtInt(x.support)}`]; }}));
    // Classifier picker for the confusion matrix and feature importance
    if (!picked || !sr.some(r => keyOf(r) === picked)) picked = keyOf(byScore[0]);
    clfSel.replaceChildren(...byScore.map(r => el("option", {value: keyOf(r), text: nameOf(r)})));
    clfSel.value = picked;
    const det = details[picked], name = nameOf(sr.find(r => keyOf(r) === picked));
    const cm = det.confusion_matrix, labels = det.confusion_matrix_labels || [];
    if (Array.isArray(cm) && cm.length) {
      const rowSum = cm.map(row => row.reduce((a, b) => a + b, 0) || 1);
      const L = labels.map(String);
      cmBox.replaceChildren(el("p", {class: "hint", text: `${name}. Rows are the true class, columns the prediction; shading is ` +
        "the share of each true class, so small classes read as clearly as large ones."}),
        heatmap({rows: L, cols: L, rowHead: "True ↓ / Predicted →", value: (r, c) => cm[L.indexOf(r)][L.indexOf(c)] / rowSum[L.indexOf(r)],
          text: (v, r, c) => fmtTick(cm[L.indexOf(r)][L.indexOf(c)]), domain: [0, 1], caption: "share of the true class",
          tip: (v, r, c) => [`${fmtInt(cm[L.indexOf(r)][L.indexOf(c)])} rows`, `${pct(v)} of true ${r}`]}));
    } else cmBox.replaceChildren(empty("No confusion matrix recorded."));
    const fi = det.feature_importance;
    if (fi && Object.keys(fi).length) {
      const signed = Object.values(fi).some(v => v < 0);
      const top = Object.entries(fi).map(([k, v]) => [k, Math.abs(v)]).sort((a, b) => b[1] - a[1]).slice(0, 15);
      fiBox.replaceChildren(el("p", {class: "hint", text: signed
        ? `${name} reports signed coefficients; bars show their magnitude. Top 15 of ${Object.keys(fi).length}.`
        : `${name}, top 15 of ${Object.keys(fi).length} features.`}), barList(top));
    } else fiBox.replaceChildren(empty(`${name} doesn't record feature importance.`));
  }

  draw();
  body.append(card("Classifier comparison", el("div", {class: "row"}, stageChips, sel),
    el("p", {class: "hint", text: "Bars start at zero, so near-ceiling scores look alike on purpose - the exact " +
      "value is printed on each bar and in the table below. Time metrics sort fastest first."}), chartBox));
  body.append(card("Score against training time", null, el("p", {class: "hint", text:
    "Up and to the left is better. The score axis is zoomed to the data, since dots encode position, not length."}), scatterBox));
  if (d.files.includes("benchmark_details.json")) {
    body.append(card("Per-class F1", null, perClassBox),
      el("div", {class: "grid g2"}, card("Confusion matrix", clfSel, cmBox), card("Feature importance", null, fiBox)));
    perClassBox.replaceChildren(el("div", {class: "loading", text: "Loading per-class detail…"}));
    try {
      const r = await fetch("/files/" + id + "/benchmark_details.json");
      if (!r.ok) throw new Error("benchmark_details.json couldn't be read");
      details = await r.json();
      drawDetail();
    } catch (e) { perClassBox.replaceChildren(errorBox(e.message)); }
  }
  body.append(card("All results", null,
    dataTable([{key: "stage", label: "Stage"}, {key: "classifier", label: "Classifier"}, {key: "scaling", label: "Scaling"},
      {key: "sampling", label: "Sampling"},
      ...metrics.map(([k]) => ({key: k, label: label[k], num: true,
        render: r => r[k] == null ? "n/a" : r[k].toFixed(k.endsWith("_s") ? 2 : 4)}))],
      rows, {initial: [metrics[0][0], -1]})));
}
function classifierChart(pts, metric, nameOf) {
  const time = metric.endsWith("_s");
  const max = time ? Math.max(...pts.map(p => p[metric])) || 1 : 1;
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const fmt = (v) => v.toFixed(time ? 2 : 4);
  return el("div", {class: "hbars", role: "list", "aria-label": "Classifier scores"},
    ...pts.map(p => {
      const name = nameOf(p);
      return withTip(el("div", {class: "hb-row", role: "listitem"},
        el("span", {class: "hb-label", title: name, text: name}),
        el("div", {class: "hb-track gridded"}, el("span", {class: "hb-seg acc", style: {width: (100 * p[metric] / max) + "%"}})),
        el("span", {class: "hb-val", text: fmt(p[metric])})),
        name, METRICS.filter(([k]) => p[k] != null).map(([k, t]) => `${t}: ${p[k].toFixed(k.endsWith("_s") ? 2 : 4)}`));
    }),
    el("div", {class: "hb-row axis", "aria-hidden": "true"}, el("span"),
      el("div", {class: "hb-ticks"}, ...ticks.map(t => el("span", {style: {left: (t * 100) + "%"}, text: fmtNum(+(t * max).toPrecision(3))}))),
      el("span")));
}

function renderProvenance(body, d, sc) {
  const fp = sc.dataset_fingerprint || {};
  const env = d.environment || {};
  const hashRow = (label, h) => [el("dt", {text: label}), el("dd", {class: "row"}, el("span", {class: "mono", text: h || "n/a"}),
    h ? copyBtn(h) : null)];
  const cards = [
    card("Dataset fingerprint", null, el("dl", {class: "kv"},
      el("dt", {text: "Train rows"}), el("dd", {text: fmtInt(fp.train_rows)}),
      el("dt", {text: "Test rows"}), el("dd", {text: fmtInt(fp.test_rows)}),
      el("dt", {text: "Features"}), el("dd", {text: fmtInt(fp.feature_count)}),
      ...hashRow("Train content hash", fp.train_content_hash), ...hashRow("Test content hash", fp.test_content_hash))),
    card("Software", null, el("dl", {class: "kv"},
      el("dt", {text: "IDS2Eval"}), el("dd", {text: sc.ids2eval_version || env.ids2eval?.version || "n/a"}),
      ...hashRow("Git commit", sc.ids2eval_git_commit || env.ids2eval?.git_commit),
      el("dt", {text: "Scorecard schema"}), el("dd", {text: sc.scorecard_schema_version || "n/a"}),
      el("dt", {text: "Generated"}), el("dd", {text: sc.generated_at || "n/a"}),
      el("dt", {text: "Audit stage"}), el("dd", {text: sc.audit_stage || "n/a"}),
      el("dt", {text: "Python"}), el("dd", {text: env.python_version || "n/a"}),
      el("dt", {text: "Platform"}), el("dd", {text: env.platform || "n/a"}))),
  ];
  if (env.packages) cards.push(card("Packages", null, dataTable([{key: "name", label: "Package"}, {key: "version", label: "Version"}],
    Object.entries(env.packages).map(([name, version]) => ({name, version})))));
  if (sc.previous_run_comparison) cards.push(prevRunCard(sc.previous_run_comparison, d));
  if (!sc.dataset_fingerprint && !d.environment) {
    body.append(card(null, null, empty("No provenance recorded for this run."))); return;
  }
  body.append(el("div", {class: "grid g2"}, ...cards));
}

const EXPORTS = [["SCORECARD.html", "HTML"], ["SCORECARD.md", "Markdown"], ["scorecard.json", "JSON"],
                 ["scorecard.pdf", "PDF"], ["scorecard.png", "PNG"]];
function renderScorecardTab(body, d, base) {
  const have = EXPORTS.filter(([f]) => d.files.includes(f));
  const actions = el("div", {class: "row"}, ...have.map(([f, t]) => el("a", {class: "btn", href: base + encodeURIComponent(f),
    target: "_blank", rel: "noopener", download: f.endsWith(".html") ? null : f, text: t})));
  if (d.files.includes("SCORECARD.html")) body.append(card("Scorecard", actions,
    el("iframe", {src: base + "SCORECARD.html", title: "Scorecard"})));
  else if (d.scorecard) body.append(card("Scorecard", actions, el("p", {class: "hint",
    text: "This run predates the HTML scorecard - use the exports above, or the Overview and Checks tabs."})));
  else body.append(card(null, null, empty("No scorecard: the audit was skipped or the run didn't get that far.")));
}
function renderFiles(body, d, base) {
  body.append(card("Run artifacts", null, el("p", {class: "hint mono", text: d.output_dir + "/runs/" + d.name}),
    el("div", {class: "files"}, ...d.files.map(f => el("a", {href: base + encodeURIComponent(f), target: "_blank",
      rel: "noopener", class: "mono", title: f, text: f})))));
}

// ---------- new run ----------

async function configFromRun(id) {
  // resolved_config.json is JSON, and JSON is valid YAML, so the editor and
  // the server's YAML loader both take it as-is.
  const r = await fetch("/files/" + id + "/resolved_config.json");
  if (!r.ok) throw new Error("That run has no resolved_config.json");
  return JSON.stringify(await r.json(), null, 2) + "\n";
}
function configPicker(onPick, withStarter) {
  const sources = runs.filter(r => r.files.includes("resolved_config.json"));
  const s = el("select", {"aria-label": "Load a config"},
    el("option", {value: "", text: "Load config from…"}),
    withStarter ? el("option", {value: "@starter", text: "Starter template (every field documented)"}) : null,
    ...sources.slice(0, 40).map(r => el("option", {value: r.id, text: `${r.dataset || "(unnamed)"} · ${when(r.name)}`})));
  s.onchange = async () => {
    const v = s.value; s.value = "";
    if (!v) return;
    try { onPick(v === "@starter" ? (await api("/api/starter-config")).yaml : await configFromRun(v)); }
    catch (e) { onPick(null, e); }
  };
  return s;
}

async function renderNewRun(main) {
  setCrumbs(["New run"]);
  if (editor.text === null) editor.text = (await api("/api/starter-config")).yaml;
  const ta = el("textarea", {spellcheck: "false", "aria-label": "Config YAML"});
  ta.value = editor.text;
  const steps = ["Edit config", "Validate", "Run", "Done"].map(t => el("div", {text: t}));
  let validated = false;
  const setStep = (i, bad) => steps.forEach((s, j) => { s.className = j < i ? "done" : j === i ? (bad ? "bad" : "active") : ""; });
  setStep(0);
  ta.addEventListener("input", () => { editor.text = ta.value; if (validated) { validated = false; setStep(0); } });
  const skipAudit = el("input", {type: "checkbox"}), skipBench = el("input", {type: "checkbox"});
  const msg = el("span", {class: "msg"});
  const setMsg = (t, cls) => { msg.textContent = t; msg.className = "msg " + (cls || ""); };
  const runBtn = el("button", {class: "primary", text: "▶ Run"}), stopBtn = el("button", {text: "■ Stop"});
  const valBtn = el("button", {text: "Validate"});
  const log = el("pre", {class: "log", text: "No run started from this page yet."});
  const jobBadge = el("span");
  const loader = configPicker((text, err) => {
    if (err) return setMsg(err.message, "err");
    ta.value = editor.text = text; validated = false; setStep(0); setMsg("Loaded.", "ok");
  }, true);

  valBtn.onclick = async () => {
    try {
      const r = await api("/api/validate", {yaml: ta.value});
      validated = r.ok;
      if (r.ok) { setStep(2); setMsg(`Valid. Runs will be written under ${r.output_dir}/runs/`, "ok"); }
      else { setStep(1, true); setMsg(r.error, "err"); }
    } catch (e) { setStep(1, true); setMsg(e.message, "err"); }
  };
  runBtn.onclick = async () => {
    try {
      await api("/api/run", {yaml: ta.value, skip_audit: skipAudit.checked, skip_benchmark: skipBench.checked});
      setMsg("Running…"); poll();
    } catch (e) { setStep(1, true); setMsg(e.message, "err"); }
  };
  stopBtn.onclick = () => api("/api/job/stop", {}).catch(e => setMsg(e.message, "err"));

  function show(job) {
    if (job.log.length) log.textContent = job.log.join("\n");
    log.scrollTop = log.scrollHeight;
    runBtn.disabled = job.state === "running"; stopBtn.disabled = job.state !== "running";
    jobBadge.replaceChildren(job.state === "running" ? el("span", {class: "badge s-running", text: "Running"})
      : job.state === "completed" ? statusBadge("ok", "Completed") : job.state === "failed"
      ? statusBadge("flag", `Failed (exit ${job.returncode})`) : el("span", {class: "badge s-none", text: "Idle"}));
    if (job.state === "running") setStep(2);
    if (job.state === "completed") {
      setStep(4); setMsg("Run completed. ", "ok");
      msg.append(el("button", {text: "Open the run →", onclick: async () => {
        await loadRuns(); if (runs.length) location.hash = runHref(runs[0].id); }}));
    }
    if (job.state === "failed") { setStep(3, true); setMsg(`Run failed (exit ${job.returncode}) - see the log.`, "err"); }
  }
  async function poll() {
    clearTimeout(pollTimer);
    let job; try { job = await api("/api/job"); } catch { return; }
    if (parseHash().page !== "new") return;
    show(job);
    if (job.state === "running") pollTimer = setTimeout(poll, 1000);
  }

  main.replaceChildren(
    pageHead("New run", "Edit the YAML config, validate it with the CLI's own checks, then launch. " +
      "Relative paths resolve against the directory the dashboard was started in."),
    el("div", {class: "wizard"}, ...steps),
    el("div", {class: "grid g2"},
      card("Config", loader, ta,
        el("div", {class: "row"}, el("label", {}, skipAudit, " skip audit"), el("label", {}, skipBench, " skip benchmark"),
          el("span", {class: "spacer"}), valBtn, runBtn, stopBtn),
        msg),
      card("Run log", jobBadge, log)));
  poll();
}

// ---------- compare ----------

function renderCompare(main) {
  setCrumbs(["Compare datasets"]);
  const mk = (label) => {
    const ta = el("textarea", {spellcheck: "false", "aria-label": label + " YAML", placeholder: label + " YAML"});
    const picker = configPicker((t, err) => { if (err) setMsg(err.message, "err"); else ta.value = t; }, false);
    return [ta, card(label, picker, ta)];
  };
  const [taA, cardA] = mk("Config A"), [taB, cardB] = mk("Config B");
  const msg = el("span", {class: "msg"});
  const setMsg = (t, cls) => { msg.textContent = t; msg.className = "msg " + (cls || ""); };
  const out = el("pre", {class: "log", text: "No comparison run yet."});
  const verdict = el("span");
  const cmpBtn = el("button", {class: "primary", text: "Compare"});
  cmpBtn.onclick = async () => {
    cmpBtn.disabled = true; setMsg("Loading both datasets - this is as heavy as the CLI command…");
    try {
      const r = await api("/api/compare-datasets", {yaml_a: taA.value, yaml_b: taB.value});
      out.textContent = r.report; setMsg("");
      verdict.replaceChildren(r.result.combined_content_match ? statusBadge("ok", "Equivalent") : statusBadge("flag", "Not equivalent"));
    } catch (e) { setMsg(e.message, "err"); }
    finally { cmpBtn.disabled = false; }
  };
  main.replaceChildren(
    pageHead("Compare datasets", "Check whether two configs load equivalent data - same as `ids2eval compare-datasets`."),
    el("div", {class: "grid g2"}, cardA, cardB),
    el("div", {class: "row"}, cmpBtn, verdict, msg),
    card("Report", null, out));
}

// ---------- chrome ----------

const THEMES = [[null, "Auto", "Theme: follows the system"], ["light", "Light", "Theme: light"],
                ["dark", "Dark", "Theme: dark"]];
function applyTheme(t) {
  if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  const [, icon, label] = THEMES.find(([k]) => k === t) || THEMES[0];
  $("#theme").textContent = icon; $("#theme").title = label; $("#theme").setAttribute("aria-label", label);
}
applyTheme(store.get("ids2eval.theme"));
$("#theme").onclick = () => {
  const i = THEMES.findIndex(([k]) => k === (store.get("ids2eval.theme") || null));
  const next = THEMES[(i + 1) % THEMES.length][0];
  store.set("ids2eval.theme", next); applyTheme(next);
};
$("#menu").onclick = () => $("#sidebar").classList.toggle("open");
$("#refresh").onclick = async () => { await loadRuns(); route(); };
window.addEventListener("hashchange", route);
api("/api/check-info").then(ci => { checkInfo = ci; }).catch(() => {}).finally(route);
