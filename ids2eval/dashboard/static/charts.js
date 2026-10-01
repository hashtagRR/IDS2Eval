"use strict";
// Chart kit for the dashboard, plus the per-check evidence views built on it.
// Charts are SVG drawn at the container's real pixel width and redrawn on
// resize, so text stays 12px instead of scaling with a viewBox. Colors come
// from CSS classes (c-s1 = train / primary series, c-s2 = test, c-ref =
// reference or control), so dark mode needs nothing here. Loaded before
// app.js, and uses its el(), withTip() and fmtNum() only at call time.

function S(tag, attrs = {}, ...kids) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "text") n.textContent = v; else n.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) n.append(k);
  return n;
}

// Re-run build(width) whenever the host's width changes; stops observing
// once the host has left the page.
function responsive(build) {
  const host = el("div", {class: "plot"});
  let last = 0;
  const ro = new ResizeObserver(() => {
    if (!host.isConnected) { ro.disconnect(); return; }
    const w = Math.floor(host.clientWidth);
    if (!w || Math.abs(w - last) < 4) return;
    last = w;
    host.replaceChildren(build(w));
  });
  ro.observe(host);
  return host;
}

// ---------- scales, ticks, formats ----------

function scale([d0, d1], [r0, r1], log) {
  if (log) {
    const a = Math.log10(d0), b = Math.log10(d1);
    return v => r0 + ((Math.log10(Math.max(v, d0)) - a) / (b - a || 1)) * (r1 - r0);
  }
  return v => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
}
function ticks([lo, hi], log, n = 5) {
  if (log) {
    const out = [];
    for (let e = Math.ceil(Math.log10(lo) - 1e-9); e <= Math.floor(Math.log10(hi) + 1e-9); e++) out.push(10 ** e);
    const step = Math.ceil(out.length / 7);
    return out.filter((_, i) => i % step === 0);
  }
  const raw = (hi - lo) / n || 1, p = 10 ** Math.floor(Math.log10(raw)), m = raw / p;
  const step = (m < 1.5 ? 1 : m < 3 ? 2 : m < 7 ? 5 : 10) * p;
  const out = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(10));
  return out;
}
function logDomain(vals) {
  const pos = vals.filter(v => v > 0);
  if (!pos.length) return [1, 10];
  const lo = 10 ** Math.floor(Math.log10(Math.min(...pos))), hi = 10 ** Math.ceil(Math.log10(Math.max(...pos)));
  return [lo, hi > lo ? hi : lo * 10];
}
// Padded data range for position encodings (dots, scatter) - bars never use this.
function padDomain(vals, {zero = false, unit = false} = {}) {
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || Math.max(Math.abs(hi) * 0.02, 0.005);
  lo -= pad; hi += pad;
  if (unit) { lo = Math.max(0, lo); hi = Math.min(1, hi); }
  if (zero) { lo = Math.min(0, lo); hi = Math.max(0, hi); }
  return [lo, hi];
}
function fmtTick(v) {
  const a = Math.abs(v);
  if (a >= 1e9) return +(v / 1e9).toPrecision(3) + "B";
  if (a >= 1e6) return +(v / 1e6).toPrecision(3) + "M";
  if (a >= 1e3) return +(v / 1e3).toPrecision(3) + "k";
  return String(+v.toPrecision(3));
}
const pct = (v) => v == null ? "n/a" : (v * 100).toFixed(Math.abs(v) < 0.01 && v !== 0 ? 2 : 1) + "%";
const trunc = (s, n) => s.length > n ? s.slice(0, Math.max(1, n - 1)) + "…" : s;

const TRAIN_TEST = [{key: "train", label: "Train", cls: "s1"}, {key: "test", label: "Test", cls: "s2"}];
const ONE = (label) => [{key: "v", label, cls: "s1"}];

function legend(series, refs = []) {
  return el("div", {class: "legend"},
    ...series.map(s => el("span", {}, el("i", {class: "sw-dot c-" + s.cls}), s.label)),
    ...refs.filter(r => r.label).map(r => el("span", {}, el("i", {class: "sw-line"}), r.label)));
}
function stats(items) {
  const shown = items.filter(([, v]) => v != null && v !== "");
  return shown.length ? el("div", {class: "stats"}, ...shown.map(([k, v, status]) =>
    el("div", {class: "stat" + (status ? " s-" + status : "")}, el("span", {text: k}), el("b", {text: String(v)})))) : null;
}

// ---------- dot plot / dumbbell ----------

// One row per category, one dot per series, a connector when there are
// several. Position-only encoding, so a zoomed axis is honest here.
function dotPlot({rows, series, log = false, domain, xLabel, refs = [], fmt, unit = false}) {
  const f = fmt || (unit ? pct : fmtNum);
  const all = rows.flatMap(r => series.map(s => r.values[s.key])).filter(v => v != null && isFinite(v));
  if (!all.length) return null;
  const dom = domain || (log ? logDomain(all) : padDomain([...all, ...refs.map(r => r.value)], {unit}));
  const rowH = 24, top = 4, axisH = xLabel ? 38 : 22;
  const plot = responsive(W => {
    const labelW = Math.min(230, Math.max(90, W * 0.34)), x0 = labelW + 14, x1 = W - 14;
    const x = scale(dom, [x0, x1], log), bottom = top + rows.length * rowH;
    const svg = S("svg", {class: "chart", width: W, height: bottom + axisH, role: "img", "aria-label": xLabel || "Dot plot"});
    for (const t of ticks(dom, log)) svg.append(
      S("line", {class: "grid-line", x1: x(t), x2: x(t), y1: top, y2: bottom}),
      S("text", {class: "tick", x: x(t), y: bottom + 14, "text-anchor": "middle", text: unit ? pct(t) : fmtTick(t)}));
    if (xLabel) svg.append(S("text", {class: "axis-label", x: (x0 + x1) / 2, y: bottom + 32, "text-anchor": "middle", text: xLabel}));
    rows.forEach((r, i) => {
      const cy = top + i * rowH + rowH / 2;
      const vals = series.map(s => [s, r.values[s.key]]).filter(([, v]) => v != null && isFinite(v));
      const hit = S("rect", {class: "hit", x: 0, y: cy - rowH / 2, width: W, height: rowH, rx: 4});
      const icon = r.mark ? (STATUS[r.mark]?.icon || "") + " " : "";
      const g = S("g", {}, hit, S("text", {class: "row-label" + (r.mark ? " mark-" + r.mark : ""), x: labelW, y: cy + 4,
        "text-anchor": "end", text: icon + trunc(r.label, Math.floor(labelW / 6.6) - icon.length)}));
      if (vals.length > 1) {
        const xs = vals.map(([, v]) => x(v));
        g.append(S("line", {class: "connector", x1: Math.min(...xs), x2: Math.max(...xs), y1: cy, y2: cy}));
      }
      for (const [s, v] of vals) g.append(S("circle", {class: "dot-mark c-" + s.cls, cx: x(v), cy, r: 5}));
      withTip(hit, r.label, [...vals.map(([s, v]) => `${s.label}: ${f(v)}`), ...(r.tip || [])]);
      svg.append(g);
    });
    for (const ref of refs) svg.append(S("line", {class: "ref-line", x1: x(ref.value), x2: x(ref.value), y1: top - 2, y2: bottom}));
    return svg;
  });
  return el("div", {class: "viz"}, series.length > 1 || refs.some(r => r.label) ? legend(series.length > 1 ? series : [], refs) : null, plot);
}

// Many values on one line (per-seed results), with an optional interval band.
function stripPlot({values, band, refs = [], xLabel, fmt = fmtNum, name = "Value"}) {
  if (!values.length) return null;
  const dom = padDomain([...values, ...refs.map(r => r.value), ...(band || [])], {zero: true});
  const plot = responsive(W => {
    const x0 = 14, x1 = W - 14, x = scale(dom, [x0, x1]), cy = 34, H = 92;
    const svg = S("svg", {class: "chart", width: W, height: H, role: "img", "aria-label": xLabel || "Strip plot"});
    for (const t of ticks(dom, false)) svg.append(
      S("line", {class: "grid-line", x1: x(t), x2: x(t), y1: 8, y2: 60}),
      S("text", {class: "tick", x: x(t), y: 74, "text-anchor": "middle", text: fmtTick(t)}));
    if (band) svg.append(S("rect", {class: "band", x: x(band[0]), y: cy - 14, width: Math.max(2, x(band[1]) - x(band[0])), height: 28, rx: 4}));
    for (const r of refs) svg.append(S("line", {class: "ref-line", x1: x(r.value), x2: x(r.value), y1: 6, y2: 62}),
      r.short ? S("text", {class: "ref-text", x: x(r.value) + 4, y: 14, text: r.short}) : null);
    values.forEach((v, i) => {
      const c = S("circle", {class: "dot-mark c-s1 hit-dot", cx: x(v), cy, r: 5});
      svg.append(c);
      withTip(c, `${name} ${i + 1}`, [fmt(v)]);
    });
    if (xLabel) svg.append(S("text", {class: "axis-label", x: (x0 + x1) / 2, y: 89, "text-anchor": "middle", text: xLabel}));
    return svg;
  });
  const keys = [];
  if (band) keys.push(el("span", {}, el("i", {class: "sw-band"}), "95% interval"));
  for (const r of refs) if (r.label) keys.push(el("span", {}, el("i", {class: "sw-line"}), r.label));
  return el("div", {class: "viz"}, keys.length ? el("div", {class: "legend"}, el("span", {}, el("i", {class: "sw-dot c-s1"}), name), ...keys) : null, plot);
}

// ---------- scatter ----------

// One series; points on the upper-left frontier (better score for less x)
// get direct labels, the rest are readable through the tooltip and table.
function scatter({points, xLog = false, xLabel, yLabel, xFmt = fmtNum, yFmt = fmtNum, unitY = false}) {
  if (points.length < 2) return null;
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const xd = xLog ? logDomain(xs) : padDomain(xs, {zero: true}), yd = padDomain(ys, {unit: unitY});
  const sorted = [...points].sort((a, b) => a.x - b.x);
  const frontier = new Set();
  let best = -Infinity;
  for (const p of sorted) if (p.y > best) { best = p.y; frontier.add(p); }
  const plot = responsive(W => {
    const H = 300, l = 54, r = W - 16, t = 10, b = H - 44;
    const x = scale(xd, [l, r], xLog), y = scale(yd, [b, t]);
    const svg = S("svg", {class: "chart", width: W, height: H, role: "img", "aria-label": `${yLabel} against ${xLabel}`});
    for (const v of ticks(xd, xLog)) svg.append(S("line", {class: "grid-line", x1: x(v), x2: x(v), y1: t, y2: b}),
      S("text", {class: "tick", x: x(v), y: b + 15, "text-anchor": "middle", text: fmtTick(v)}));
    for (const v of ticks(yd, false)) svg.append(S("line", {class: "grid-line", x1: l, x2: r, y1: y(v), y2: y(v)}),
      S("text", {class: "tick", x: l - 6, y: y(v) + 4, "text-anchor": "end", text: unitY ? (+v.toFixed(4)).toString() : fmtTick(v)}));
    svg.append(S("text", {class: "axis-label", x: (l + r) / 2, y: H - 6, "text-anchor": "middle", text: xLabel}),
      S("text", {class: "axis-label", x: 12, y: (t + b) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${(t + b) / 2})`, text: yLabel}));
    for (const p of points) {
      const cx = x(p.x), cy = y(p.y);
      const hit = S("circle", {class: "hit", cx, cy, r: 13});
      svg.append(hit, S("circle", {class: "dot-mark c-s1", cx, cy, r: 6}));
      if (frontier.has(p)) svg.append(S("text", {class: "point-label", x: cx + (cx > r - 120 ? -10 : 10), y: cy - 9,
        "text-anchor": cx > r - 120 ? "end" : "start", text: p.label}));
      withTip(hit, p.label, [`${yLabel}: ${yFmt(p.y)}`, `${xLabel}: ${xFmt(p.x)}`, ...(p.tip || [])]);
    }
    return svg;
  });
  return el("div", {class: "viz"}, el("div", {class: "legend"}, el("span", {}, el("i", {class: "sw-dot c-s1"}), "Classifier"),
    el("span", {class: "hint", text: "labelled: best score at or below that cost"})), plot);
}

// ---------- heatmap ----------

// HTML table so it reflows; one blue ramp, value printed in each cell while
// the grid is small enough to read them.
function heatmap({rows, cols, value, text, domain = [0, 1], rowHead = "", tip, caption}) {
  const [lo, hi] = domain;
  const showText = cols.length <= 16;
  const head = el("tr", {}, el("th", {class: "corner", text: rowHead}),
    ...cols.map(c => el("th", {class: "col", scope: "col", title: c}, el("span", {text: trunc(c, 22)}))));
  const body = rows.map(r => el("tr", {}, el("th", {class: "rowh", scope: "row", title: r, text: trunc(r, 32)}), ...cols.map(c => {
    const v = value(r, c);
    if (v == null || !isFinite(v)) return el("td", {class: "hcell empty-cell", text: "–"});
    const p = Math.round(100 * Math.min(1, Math.max(0, (v - lo) / (hi - lo || 1))));
    const td = el("td", {class: "hcell" + (p > 55 ? " dark" : ""), style: {
      background: `color-mix(in oklab, var(--seq-hi) ${p}%, var(--seq-lo))`}, text: showText ? text(v, r, c) : ""});
    withTip(td, `${r} · ${c}`, tip ? tip(v, r, c) : [text(v, r, c)]);
    return td;
  })));
  return el("div", {class: "viz"},
    el("div", {class: "legend"}, el("span", {text: fmtTick(lo)}), el("i", {class: "seq-bar"}), el("span", {text: fmtTick(hi)}),
      caption ? el("span", {class: "hint", text: caption}) : null),
    el("div", {class: "tablewrap heatwrap"}, el("table", {class: "heat"}, el("thead", {}, head), el("tbody", {}, ...body))));
}

// ---------- composition bar ----------

// Horizontal 100% bars of named parts (kept vs removed rows).
function splitBars(rows, parts) {
  return el("div", {class: "viz"}, legend(parts.map(p => ({label: p.label, cls: p.cls}))),
    el("div", {class: "hbars"}, ...rows.map(r => {
      const total = parts.reduce((s, p) => s + (r[p.key] || 0), 0) || 1;
      const removed = total - (r[parts[0].key] || 0);
      return withTip(el("div", {class: "hb-row"},
        el("span", {class: "hb-label", text: r.label}),
        el("div", {class: "hb-track"}, ...parts.filter(p => r[p.key]).map(p =>
          el("span", {class: "hb-seg c-" + p.cls, style: {flexGrow: String(r[p.key] / total), flexBasis: "0"}}))),
        el("span", {class: "hb-val", text: removed ? "−" + pct(removed / total) : "0%"})),
        r.label, parts.filter(p => r[p.key] != null).map(p => `${p.label}: ${fmtInt(r[p.key])} (${pct((r[p.key] || 0) / total)})`));
    })));
}

// ---------- per-check evidence views ----------

// Each returns a list of nodes (or []) for a check's recorded details;
// `before` is the pre-deduplication report, which is where dedup_check's
// per-class rates live (after dedup they're zero by construction).
const CHECK_VIZ = {
  class_distribution_report(d) {
    const tr = d.train?.counts || {}, te = d.test?.counts || {};
    const classes = [...new Set([...Object.keys(tr), ...Object.keys(te)])].sort((a, b) => (tr[b] || 0) - (tr[a] || 0));
    if (!classes.length) return [];
    const rare = new Set(d.rare_classes || []);
    return [stats([["Classes", classes.length], ["Imbalance (majority:minority)",
        d.imbalance_ratio != null ? fmtNum(Math.round(d.imbalance_ratio)) + ":1" : null],
        ["Rare classes (<1% of train)", rare.size, rare.size ? "warning" : null]]),
      dotPlot({rows: classes.map(c => ({label: c, values: {train: tr[c], test: te[c]}, mark: rare.has(c) ? "warning" : null,
        tip: [`Train share: ${pct(d.train?.shares?.[c])}`, ...(rare.has(c) ? ["Below 1% of train"] : [])]})),
        series: TRAIN_TEST, log: true, xLabel: "Rows per class (log scale)", fmt: fmtInt})];
  },
  dedup_check(d, before) {
    const src = before && before.by_class ? before : d;
    return [dedupComposition(src), dedupByClass(src)].filter(Boolean);
  },
  label_conflict_check(d) {
    const by = d.by_class || {};
    const rows = Object.entries(by).filter(([, v]) => v.conflicting_rate != null)
      .sort((a, b) => b[1].conflicting_rate - a[1].conflicting_rate)
      .map(([c, v]) => ({label: c, values: {v: v.conflicting_rate}}));
    return [stats([["Conflicting groups", d.conflicting_groups != null ? fmtInt(d.conflicting_groups) : null],
        ["Conflicting rows", d.conflicting_rows != null ? fmtInt(d.conflicting_rows) : null],
        ["Groups spanning train and test", d.cross_split_conflicting_groups != null ? fmtInt(d.cross_split_conflicting_groups) : null]]),
      rows.length ? dotPlot({rows, series: ONE("Rows with a conflicting label"), unit: true,
        domain: [0, Math.max(...rows.map(r => r.values.v), 0.01) * 1.08], xLabel: "Share of the class's rows in a conflicting group"}) : null]
      .filter(Boolean);
  },
  feature_auc_ranking_check(d) {
    const top = Object.entries(d.top_features || {});
    if (!top.length) return [];
    return [stats([["Best feature", d.best_feature], ["Class it separates", d.best_class]]),
      dotPlot({rows: top.map(([f, v]) => ({label: f, values: {v}, mark: f === d.best_feature ? "flag" : null})),
        series: ONE("Standalone AUC"), domain: [0.5, 1], fmt: v => v.toFixed(4), xLabel: "Standalone ROC AUC (0.5 = chance)"})];
  },
  identity_column_flag(d) {
    const auc = Object.entries(d.standalone_auc || {});
    if (!auc.length) return [];
    const drop = new Set(d.suggested_drop || []);
    const out = [dotPlot({rows: auc.sort((a, b) => b[1] - a[1]).map(([c, v]) => ({label: c, values: {v},
        mark: drop.has(c) ? "flag" : null, tip: drop.has(c) ? ["Suggested to drop"] : []})),
      series: ONE("Standalone AUC"), domain: [0.5, 1], fmt: v => v.toFixed(3), xLabel: "Standalone ROC AUC (0.5 = chance)"})];
    const by = d.by_class || {};
    const cols = Object.keys(by), classes = [...new Set(cols.flatMap(c => Object.keys(by[c] || {})))];
    if (cols.length && classes.length) out.push(el("h3", {text: "AUC per class (one class against the rest)"}),
      heatmap({rows: cols, cols: classes, value: (r, c) => by[r]?.[c], text: v => v.toFixed(2), domain: [0.5, 1],
        rowHead: "Column", caption: "values below 0.5 shown at the lightest step"}));
    return out;
  },
  one_rule_check(d) {
    if (d.train_accuracy == null && d.test_accuracy == null) return [];
    return [stats([["Rule", d.rule]]),
      dotPlot({rows: [{label: "Accuracy of the single rule", values: {train: d.train_accuracy, test: d.test_accuracy}}],
        series: TRAIN_TEST, unit: true, domain: [0, 1], xLabel: "Accuracy"})];
  },
  homogeneity_test(d) {
    const per = Object.entries(d.per_class || {});
    if (!per.length) return [];
    const hits = per.filter(([, v]) => v.leakage_signature).length;
    return [stats([["Classes tested", per.length], ["Leakage signature", hits, hits ? "flag" : "ok"]]),
      dotPlot({rows: per.sort((a, b) => b[1].test_near_zero_rate - a[1].test_near_zero_rate).map(([c, v]) => ({label: c,
        values: {test: v.test_near_zero_rate, control: v.control_near_zero_rate}, mark: v.leakage_signature ? "flag" : null,
        tip: [`p = ${v.p_value != null ? v.p_value.toPrecision(3) : "n/a"}`, ...(v.leakage_signature ? ["Leakage signature (p < 0.05)"] : [])]})),
        series: [{key: "test", label: "Test rows", cls: "s2"}, {key: "control", label: "Control", cls: "ref"}],
        unit: true, xLabel: "Share with a near-zero nearest-neighbour distance to train"})];
  },
  row_order_leakage_check(d) {
    const c = d.contiguity_ratio;
    if (!c) return [];
    return [dotPlot({rows: [{label: "Label contiguity", values: {train: c.train, test: c.test}}], series: TRAIN_TEST,
      domain: [0, 1], fmt: v => v.toFixed(4), xLabel: "Contiguity ratio (higher = rows grouped by label)"})];
  },
  repeated_seed_falsification_check(d) {
    const drops = d.drops_by_seed || [];
    if (!drops.length) return [];
    const refs = [{value: 0}];
    if (d.materiality_threshold != null) refs.push({value: d.materiality_threshold, label: "Materiality threshold",
      short: "threshold"});
    return [stats([["Seeds", d.n_seeds ?? drops.length], ["Mean drop", d.mean_drop != null ? d.mean_drop.toPrecision(3) : null],
        ["95% interval", d.ci_95 ? d.ci_95.map(v => v.toPrecision(3)).join(" to ") : null],
        ["Material", d.material == null ? null : d.material ? "yes" : "no", d.material ? "flag" : "ok"]]),
      stripPlot({values: drops, band: d.ci_95, refs, name: "Seed", fmt: v => v.toPrecision(4), xLabel: "Accuracy drop per seed"})];
  },
  resplit_falsification(d) {
    if (d.random_accuracy == null) return [];
    return [stats([["Drop", d.drop != null ? d.drop.toPrecision(3) : null]]),
      dotPlot({rows: [{label: "Random split", values: {v: d.random_accuracy}}, {label: "Grouped split", values: {v: d.grouped_accuracy}}],
        series: ONE("Accuracy"), fmt: v => v.toFixed(5), xLabel: "Accuracy (axis zoomed to the data)"})];
  },
  result_robustness_check(d) {
    const by = Object.entries(d.accuracy_by_condition || {});
    if (!by.length) return [];
    return [stats([["Spread", d.spread != null ? d.spread.toPrecision(3) : null], ["Best", d.best_condition?.replace(/_/g, " ")],
        ["Worst", d.worst_condition?.replace(/_/g, " ")]]),
      dotPlot({rows: by.sort((a, b) => b[1] - a[1]).map(([c, v]) => ({label: c.replace(/_/g, " "), values: {v}})),
        series: ONE("Accuracy"), fmt: v => v.toFixed(4), xLabel: "Accuracy (axis zoomed to the data)"})];
  },
};
function checkViz(check, details, before) {
  const f = CHECK_VIZ[check];
  if (!f || !details) return [];
  try { return f(details, before).filter(Boolean); } catch (e) { console.warn("viz failed for", check, e); return []; }
}

function dedupComposition(d) {
  if (d.train_rows_raw == null) return null;
  return splitBars([
    {label: "Train", kept: d.train_rows_deduped, dup: d.train_duplicates_dropped},
    {label: "Test", kept: d.test_rows_deduped, leak: d.test_leakage_dropped, dup: d.test_duplicates_dropped},
  ], [{key: "kept", label: "Kept", cls: "s1"}, {key: "leak", label: "Test row matching a train row", cls: "s2"},
      {key: "dup", label: "Duplicate within split", cls: "ref"}]);
}
function dedupByClass(d) {
  const by = Object.entries(d.by_class || {});
  if (!by.length || by.every(([, v]) => !v.train_duplicate_rate && !v.test_leak_rate)) return null;
  return dotPlot({rows: by.sort((a, b) => Math.max(b[1].train_duplicate_rate || 0, b[1].test_leak_rate || 0) -
      Math.max(a[1].train_duplicate_rate || 0, a[1].test_leak_rate || 0))
    .map(([c, v]) => ({label: c, values: {train: v.train_duplicate_rate, test: v.test_leak_rate}})),
    series: [{key: "train", label: "Train duplicate rate", cls: "s1"}, {key: "test", label: "Test rows leaking a train match", cls: "s2"}],
    unit: true, domain: [0, Math.min(1, Math.max(...by.flatMap(([, v]) => [v.train_duplicate_rate || 0, v.test_leak_rate || 0])) * 1.08 || 1)],
    xLabel: "Share of the class's rows (before deduplication)"});
}
