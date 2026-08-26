"use strict";
/* AIPI dashboard — zero-dependency SPA.
 * Charts are hand-rolled SVG so the whole thing runs offline: no CDN, no build step.
 * Every number shown comes from the API; nothing is computed or hard-coded here. */

const API = ""; // same-origin
const PALETTE = ["#1a5fb4", "#e07b1a", "#157347", "#8e44ad", "#c0392b", "#16a085", "#2c3e50"];

async function fetchJSON(path) {
  const r = await fetch(API + path);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (_) {}
    throw new Error(`${r.status} ${detail}`);
  }
  return r.json();
}

const fmt = {
  idx: (v) => (v == null ? "—" : v.toFixed(1)),
  idx2: (v) => (v == null ? "—" : v.toFixed(2)),
  pct: (v) => (v == null ? "—" : v.toFixed(2) + "%"),
  pct1: (v) => (v == null ? "—" : v.toFixed(1) + "%"),
  int: (v) => (v == null ? "—" : v.toLocaleString()),
  signed: (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2)),
};

function el(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstChild; }

/* ---------- SVG charts ---------- */

const W = 820, H = 300, M = { t: 14, r: 16, b: 30, l: 44 };

function niceDomain(min, max) {
  if (min === max) { min -= 1; max += 1; }
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

function lineChart(node, { series, baseline = null, yfmt = fmt.idx, dateAxis = true }) {
  const allX = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort();
  const xi = new Map(allX.map((x, i) => [x, i]));
  const ys = series.flatMap((s) => s.points.map((p) => p.y));
  if (baseline != null) ys.push(baseline);
  let [ymin, ymax] = niceDomain(Math.min(...ys), Math.max(...ys));
  const n = allX.length;
  const px = (i) => M.l + (n <= 1 ? 0 : (i / (n - 1)) * (W - M.l - M.r));
  const py = (y) => M.t + (1 - (y - ymin) / (ymax - ymin)) * (H - M.t - M.b);

  const gridY = 5, grid = [];
  for (let g = 0; g <= gridY; g++) {
    const y = ymin + (g / gridY) * (ymax - ymin);
    grid.push(`<line x1="${M.l}" y1="${py(y).toFixed(1)}" x2="${W - M.r}" y2="${py(y).toFixed(1)}"/>`);
    grid.push(`<text x="${M.l - 8}" y="${(py(y) + 3).toFixed(1)}" text-anchor="end">${yfmt(y)}</text>`);
  }

  const nLabels = Math.min(6, n);
  const xlab = [];
  for (let k = 0; k < nLabels; k++) {
    const i = Math.round((k / Math.max(1, nLabels - 1)) * (n - 1));
    const raw = allX[i];
    const label = dateAxis ? String(raw).slice(5) : raw;
    xlab.push(`<text x="${px(i).toFixed(1)}" y="${H - 10}" text-anchor="middle">${label}</text>`);
  }

  const lines = series.map((s, k) => {
    const color = s.color || PALETTE[k % PALETTE.length];
    const d = s.points
      .filter((p) => xi.has(p.x))
      .map((p, j) => `${j ? "L" : "M"}${px(xi.get(p.x)).toFixed(1)},${py(p.y).toFixed(1)}`)
      .join(" ");
    return `<path class="series-line" d="${d}" stroke="${color}"/>`;
  }).join("");

  const base = baseline != null
    ? `<line class="baseline" x1="${M.l}" y1="${py(baseline).toFixed(1)}" x2="${W - M.r}" y2="${py(baseline).toFixed(1)}"/>`
    : "";

  node.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">
    <g class="grid">${grid.join("")}</g>
    ${base}
    <g class="axis">${xlab.join("")}</g>
    ${lines}
  </svg>`;
}

function barChart(node, { bars, baseline = null, yfmt = fmt.idx, color = "#1a5fb4" }) {
  const ys = bars.map((b) => b.value);
  if (baseline != null) ys.push(baseline);
  let ymin = Math.min(0, ...ys), ymax = Math.max(...ys);
  [ymin, ymax] = [ymin, ymax + (ymax - ymin) * 0.1];
  const n = bars.length;
  const bw = (W - M.l - M.r) / n * 0.62;
  const step = (W - M.l - M.r) / n;
  const py = (y) => M.t + (1 - (y - ymin) / (ymax - ymin)) * (H - M.t - M.b);

  const gridY = 5, grid = [];
  for (let g = 0; g <= gridY; g++) {
    const y = ymin + (g / gridY) * (ymax - ymin);
    grid.push(`<line x1="${M.l}" y1="${py(y).toFixed(1)}" x2="${W - M.r}" y2="${py(y).toFixed(1)}"/>`);
    grid.push(`<text x="${M.l - 8}" y="${(py(y) + 3).toFixed(1)}" text-anchor="end">${yfmt(y)}</text>`);
  }
  const rects = bars.map((b, i) => {
    const cx = M.l + step * i + step / 2;
    const y0 = py(Math.max(0, b.value)), y1 = py(Math.min(0, b.value));
    const cls = b.ref ? "bar ref" : "bar";
    return `<rect class="${cls}" x="${(cx - bw / 2).toFixed(1)}" y="${y0.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.abs(y1 - y0).toFixed(1)}" fill="${b.ref ? "#e07b1a" : color}"/>
      <text x="${cx.toFixed(1)}" y="${(y0 - 5).toFixed(1)}" text-anchor="middle" class="barval">${yfmt(b.value)}</text>
      <text x="${cx.toFixed(1)}" y="${H - 10}" text-anchor="middle">${b.label}</text>`;
  }).join("");
  const base = baseline != null
    ? `<line class="baseline" x1="${M.l}" y1="${py(baseline).toFixed(1)}" x2="${W - M.r}" y2="${py(baseline).toFixed(1)}"/>` : "";
  node.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">
    <g class="grid">${grid.join("")}</g>${base}
    <g class="axis" style="font-size:11px">${rects}</g>
  </svg>`;
  node.querySelectorAll(".barval").forEach((t) => (t.style.fontFamily = "var(--mono)"), t => t);
}

function sparkline(points, color = "#1a5fb4") {
  if (!points.length) return "";
  const w = 90, h = 22, ys = points.map((p) => p.y);
  let mn = Math.min(...ys), mx = Math.max(...ys);
  if (mn === mx) { mn -= 1; mx += 1; }
  const d = points.map((p, i) => {
    const x = (i / (points.length - 1)) * (w - 2) + 1;
    const y = h - 2 - ((p.y - mn) / (mx - mn)) * (h - 4);
    return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}

function kpi(label, val, { hint = "", cls = "", small = false } = {}) {
  return `<div class="kpi"><div class="label">${label}</div>
    <div class="val ${small ? "small" : ""} ${cls}">${val}</div>
    ${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
}

/* ---------- state ---------- */
const state = { headline: null, headlineAdj: null, routes: null, routeCache: {}, run: null };

/* ---------- provenance strip ---------- */
function renderProvenance(run, methodology, latestDate) {
  const bp = methodology.base_period;
  document.getElementById("provenance").innerHTML = `
    <div class="item"><span class="k">latest index date</span><span class="v">${latestDate || "—"}</span></div>
    <div class="item"><span class="k">base period</span><span class="v">${bp.start || "?"} … ${bp.end || "?"}</span></div>
    <div class="item"><span class="k">run id</span><span class="v">${run.run_id}</span></div>
    <div class="item"><span class="k">git sha</span><span class="v">${run.git_sha.slice(0, 10)}</span></div>
    <div class="item"><span class="k">config hash</span><span class="v">${run.config_hash.slice(0, 12)}</span></div>
    <div class="item"><span class="k">rows in → eligible</span><span class="v">${fmt.int(run.input_row_count)} → ${fmt.int(run.index_eligible_rows)}</span></div>`;
}

/* ---------- views ---------- */

async function renderHeadline() {
  if (!state.headline) state.headline = await fetchJSON("/api/v1/index");
  const d = state.headline;
  const pts = d.points;
  const first = pts[0], last = pts[pts.length - 1];
  const chg = ((last.value - 100) ).toFixed(2);
  const dir = last.value >= 100 ? "up" : "down";
  document.getElementById("headline-kpis").innerHTML =
    kpi("Latest index", fmt.idx2(last.value), { hint: last.date }) +
    kpi("Change from base", fmt.signed(last.value - 100) + " pts", { cls: dir, hint: (chg >= 0 ? "+" : "") + (100 * (last.value - 100) / 100).toFixed(2) + "% vs base=100" }) +
    kpi("Coverage (latest)", fmt.pct1(last.coverage_pct), { hint: "share of expected sample present" }) +
    kpi("Observations (latest)", fmt.int(last.n_obs), { hint: `${fmt.int(last.matched_n)} matched pairs`, small: true }) +
    kpi("Days published", fmt.int(d.count), { small: true });

  await drawHeadlineChart();
}

async function drawHeadlineChart() {
  const showAdj = document.getElementById("dow-toggle").checked;
  const series = [{ name: "Headline", color: PALETTE[0], points: state.headline.points.map((p) => ({ x: p.date, y: p.value })) }];
  let legend = `<span><span class="sw" style="background:${PALETTE[0]}"></span>Headline index</span>`;
  if (showAdj) {
    if (!state.headlineAdj) state.headlineAdj = await fetchJSON("/api/v1/index?dow_adjusted=true");
    series.push({ name: "DOW-adjusted", color: PALETTE[1], points: state.headlineAdj.points.map((p) => ({ x: p.date, y: p.value })) });
    legend += `<span><span class="sw" style="background:${PALETTE[1]}"></span>Day-of-week adjusted</span>`;
  }
  legend += `<span><span class="sw" style="background:var(--faint)"></span>Base = 100</span>`;
  lineChart(document.getElementById("headline-chart"), { series, baseline: 100, yfmt: fmt.idx });
  document.getElementById("headline-legend").innerHTML = legend;
}

async function renderRoutes() {
  if (!state.routes) state.routes = await fetchJSON("/api/v1/index/routes");
  const rows = state.routes.routes;
  const vals = rows.map((r) => r.latest_value);
  const spread = (Math.max(...vals) - Math.min(...vals)).toFixed(2);
  document.getElementById("routes-kpis").innerHTML =
    kpi("Routes tracked", fmt.int(rows.length)) +
    kpi("Highest latest index", fmt.idx2(Math.max(...vals)), { hint: rows.reduce((a, b) => (b.latest_value > a.latest_value ? b : a)).route_code, small: true }) +
    kpi("Lowest latest index", fmt.idx2(Math.min(...vals)), { hint: rows.reduce((a, b) => (b.latest_value < a.latest_value ? b : a)).route_code, small: true }) +
    kpi("Dispersion", spread + " pts", { hint: "spread across routes; why weights matter", small: true });

  const t = document.getElementById("routes-table");
  t.innerHTML = `<thead><tr>
      <th>Route</th><th>Code</th><th class="num">Weight</th>
      <th class="num">Latest index</th><th>Path</th></tr></thead>
    <tbody>${rows.map((r) => `<tr class="clickable" data-route="${r.route_code}">
      <td>${r.display_name}</td>
      <td><span class="pill">${r.route_code}</span></td>
      <td class="num">${(r.weight * 100).toFixed(2)}%</td>
      <td class="num">${fmt.idx2(r.latest_value)}</td>
      <td data-spark="${r.route_code}"></td>
    </tr>`).join("")}</tbody>`;

  t.querySelectorAll("tr.clickable").forEach((tr) =>
    tr.addEventListener("click", () => selectRoute(tr.dataset.route)));

  // sparklines (need each route series; fetch lazily but fill what we have)
  for (const r of rows) {
    const data = await routeSeries(r.route_code);
    const cell = t.querySelector(`[data-spark="${r.route_code}"]`);
    if (cell) cell.innerHTML = sparkline(data.points.map((p) => ({ y: p.value })));
  }
  if (rows.length) selectRoute(rows[0].route_code);
}

async function routeSeries(code) {
  if (!state.routeCache[code]) state.routeCache[code] = await fetchJSON(`/api/v1/index/routes/${code}`);
  return state.routeCache[code];
}

async function selectRoute(code) {
  const data = await routeSeries(code);
  document.getElementById("route-chart-title").textContent =
    `${data.display_name} · ${(data.weight * 100).toFixed(2)}% weight · latest ${fmt.idx2(data.points[data.points.length - 1].value)}`;
  lineChart(document.getElementById("route-chart"), {
    series: [{ name: code, color: PALETTE[0], points: data.points.map((p) => ({ x: p.date, y: p.value })) }],
    baseline: 100,
  });
  document.querySelectorAll("#routes-table tr").forEach((tr) =>
    tr.classList.toggle("selected", tr.dataset && tr.dataset.route === code));
}

async function renderLeadtime() {
  const curve = await fetchJSON("/api/v1/index/leadtime/curve");
  document.getElementById("leadtime-curve-note").textContent =
    `${curve.note} As at ${curve.as_of}.`;
  barChart(document.getElementById("leadtime-curve-chart"), {
    bars: curve.curve.map((p) => ({ label: p.advance_days + "d", value: p.relative_level, ref: p.advance_days === curve.reference_window })),
    baseline: 100, yfmt: fmt.idx,
  });

  const idx = await fetchJSON("/api/v1/index/leadtime");
  const series = idx.windows.map((w, k) => ({
    name: w.advance_days + "d", color: PALETTE[k % PALETTE.length],
    points: w.points.map((p) => ({ x: p.date, y: p.value })),
  }));
  lineChart(document.getElementById("leadtime-index-chart"), { series, baseline: 100 });
  document.getElementById("leadtime-index-legend").innerHTML =
    series.map((s) => `<span><span class="sw" style="background:${s.color}"></span>${s.name} to departure</span>`).join("");
}

async function renderVolatility() {
  const v = await fetchJSON("/api/v1/index/volatility");
  const se = v.sampling_error || {};
  document.getElementById("sampling-headline-card").innerHTML = se.headline
    ? `<h3>What one collection day per month costs</h3><p class="note" style="font-size:15px;color:var(--ink);line-height:1.5">${se.headline}</p>`
    : `<h3>Sampling error</h3><p class="note">Not computable: ${se.reason || "insufficient data"}.</p>`;

  const req = se.required_days_for_1pct_mae;
  document.getElementById("volatility-kpis").innerHTML =
    kpi("Daily volatility", fmt.pct(v.daily.daily_volatility_pct), { hint: "std of day-on-day % change" }) +
    kpi("Largest daily move", fmt.pct(v.daily.max_daily_move_pct), { small: true }) +
    (req ? kpi("Days/month for ±1% MAE", req.achieved ? fmt.int(req.required_days_per_month) : ">31", { hint: "to match daily accuracy by sampling", cls: "up" }) : "") +
    kpi("Flat-index alarm", v.daily.suspiciously_flat ? "TRIPPED" : "clear", { cls: v.daily.suspiciously_flat ? "up" : "down", hint: "cached-data detector", small: true });

  if (se.curve && se.curve.length) {
    const S = (key, color) => ({ name: key, color, points: se.curve.map((r) => ({ x: String(r.days_per_month), y: key === "dir" ? r.direction_error_rate * 100 : r[key] })) });
    lineChart(document.getElementById("sampling-chart"), {
      series: [S("mae_pct", PALETTE[0]), S("p95_abs_pct", PALETTE[1]), S("dir", PALETTE[4])],
      baseline: null, yfmt: fmt.pct1, dateAxis: false,
    });
    document.getElementById("sampling-legend").innerHTML =
      `<span><span class="sw" style="background:${PALETTE[0]}"></span>Mean abs error</span>
       <span><span class="sw" style="background:${PALETTE[1]}"></span>95th-pct error</span>
       <span><span class="sw" style="background:${PALETTE[4]}"></span>Wrong-direction rate</span>
       <span>x-axis: collection days per month</span>`;
  }

  const card = document.getElementById("intraday-card");
  if (v.intraday && v.intraday.available) {
    const bw = v.intraday.by_advance_window;
    const bars = Object.keys(bw).map((w) => Number(w)).sort((a, b) => a - b)
      .map((w) => ({ label: w + "d", value: bw[String(w)] }));
    barChart(document.getElementById("intraday-chart"), { bars, yfmt: fmt.pct1, color: PALETTE[2] });
    card.querySelector(".note").textContent =
      `${v.intraday.note} Based on ${fmt.int(v.intraday.offer_days_with_multiple_slots)} offer-days with multiple slots; mean CV ${fmt.pct(v.intraday.mean_intraday_cv_pct)}.`;
  } else {
    document.getElementById("intraday-chart").innerHTML =
      `<p class="note">${(v.intraday && v.intraday.note) || "No intraday data collected in this run."}</p>`;
  }
}

async function renderMethodology() {
  const m = await fetchJSON("/api/v1/methodology");
  const f = m.index_number;
  document.getElementById("methodology-formulae").innerHTML =
    `<h3>Index-number design</h3>
     <dl class="meta">
       <dt>Elementary</dt><dd>${f.elementary_aggregate}</dd>
       <dt>Multilateral</dt><dd>${f.multilateral}</dd>
       <dt>Upper level</dt><dd>${f.upper_aggregation}</dd>
       <dt>Base period</dt><dd>${f.base_period}</dd>
       <dt>Seasonal</dt><dd>${f.seasonal}</dd>
     </dl>`;

  const dg = m.diagnostics;
  document.getElementById("methodology-diagnostics").innerHTML =
    `<h3>Specification diagnostics</h3>
     <p class="note">Each is a defect a naive build would have shipped silently. Reported, not hidden.</p>
     <dl class="meta">
       <dt>Chain drift removed</dt><dd>${fmt.pct(dg.chain_drift && dg.chain_drift.end_gap_pct)} at series end (max ${fmt.pct(dg.chain_drift && dg.chain_drift.max_abs_gap_pct)})</dd>
       <dt>Composition bias</dt><dd>${fmt.pct(dg.composition_bias_pct)} (GM-of-levels vs matched Jevons)</dd>
       <dt>Day-of-week amplitude</dt><dd>${fmt.pct(dg.dow_amplitude_pct)} (weekly cycle removed)</dd>
     </dl>`;

  const c = m.cleaning;
  document.getElementById("methodology-cleaning").innerHTML =
    `<h3>Cleaning row-accounting</h3>
     <p class="note">An unexplained fall in accepted rows is indistinguishable from a fall in fares, so the accounting is part of the output.</p>
     <table class="data">
       <tbody>
         <tr><td>Rows in</td><td class="num">${fmt.int(c.rows_in)}</td></tr>
         <tr><td>Quarantined</td><td class="num">${fmt.int(c.rows_quarantined)} <span class="mono" style="color:var(--faint)">${JSON.stringify(c.quarantine_reasons)}</span></td></tr>
         <tr><td>Off index capture slot</td><td class="num">${fmt.int(c.rows_off_capture_slot)}</td></tr>
         <tr><td>Basket exclusions</td><td class="num"><span class="mono" style="color:var(--faint)">${JSON.stringify(c.basket_exclusions)}</span></td></tr>
         <tr><td>De-duplicated</td><td class="num">${fmt.int(c.rows_deduplicated)}</td></tr>
         <tr><td>Sold out (flagged, excluded)</td><td class="num">${fmt.int(c.rows_soldout)}</td></tr>
         <tr><td>Outliers flagged (kept)</td><td class="num">${fmt.int(c.outliers && c.outliers.flagged)}</td></tr>
         <tr><td><b>Index-eligible</b></td><td class="num"><b>${fmt.int(c.rows_index_eligible)}</b> (${fmt.pct1(c.retention_pct)} retention)</td></tr>
       </tbody>
     </table>`;

  const fp = m.fingerprint;
  document.getElementById("methodology-fingerprint").innerHTML =
    `<h3>Methodology fingerprint</h3>
     <p class="note">Two runs with this fingerprint on the same inputs must produce identical numbers. Any published revision is a diff against a retained vintage.</p>
     <dl class="meta">
       <dt>Base window (days)</dt><dd>${fp.base_period_days}</dd>
       <dt>GEKS window (days)</dt><dd>${fp.geks_window_days}</dd>
       <dt>Min matched items</dt><dd>${fp.min_matched_items}</dd>
       <dt>Outlier: min n / k</dt><dd>${fp.min_n_for_trim} / ${fp.mad_trim_k} (log-MAD)</dd>
       <dt>Brand family</dt><dd>${fp.basket.brand_family}</dd>
       <dt>Advance windows</dt><dd>${fp.basket.advance_windows.join(", ")} days</dd>
       <dt>Routes</dt><dd>${fp.basket.routes.length} directional pairs</dd>
       <dt>Capture slot (IST)</dt><dd>${fp.basket.index_capture_slot_ist}</dd>
     </dl>`;
}

/* ---------- tabs & init ---------- */
const RENDERERS = {
  headline: renderHeadline, routes: renderRoutes, leadtime: renderLeadtime,
  volatility: renderVolatility, methodology: renderMethodology,
};
const rendered = new Set();

function show(view) {
  document.querySelectorAll("nav.tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("active", s.id === "view-" + view));
  if (!rendered.has(view)) {
    rendered.add(view);
    RENDERERS[view]().catch((e) => {
      document.getElementById("view-" + view).insertAdjacentHTML("beforeend", `<div class="err">Failed to load: ${e.message}</div>`);
      rendered.delete(view);
    });
  }
}

async function init() {
  document.getElementById("tabs").addEventListener("click", (e) => {
    if (e.target.dataset.view) show(e.target.dataset.view);
  });
  document.getElementById("dow-toggle").addEventListener("change", drawHeadlineChart);
  window.addEventListener("resize", () => {}); // svg is viewBox-scaled; nothing to do

  try {
    const [run, methodology, health] = await Promise.all([
      fetchJSON("/api/v1/pipeline-run"),
      fetchJSON("/api/v1/methodology"),
      fetchJSON("/health"),
    ]);
    state.run = run;
    renderProvenance(run, methodology, health.latest_index_date);
  } catch (e) {
    document.getElementById("provenance").innerHTML = `<div class="err">API unreachable: ${e.message}</div>`;
  }
  show("headline");
}

init();
