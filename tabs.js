// Lazy-loaded by hub.html for the CAGR, Chips, SEMI Scorecard and Semi Holdings tabs.
(function () {
const $ = id => document.getElementById(id);
const esc = t => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const aud = (n, dp = 0) => (n < 0 ? "-" : "") + "A$" + Math.abs(n).toLocaleString("en-AU", { minimumFractionDigits: dp, maximumFractionDigits: dp });
const pct = (v, dp = 1) => v == null || !isFinite(v) ? "–" : (v >= 0 ? "+" : "") + (v * 100).toFixed(dp) + "%";
const cpct = (v, dp) => '<span class="' + (v >= 0 ? "up" : "down") + '">' + pct(v, dp) + "</span>";
const dstr = s => new Date(s + "T12:00:00Z").toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
const get = u => fetch(u, { cache: "no-store" }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
const loadScript = src => new Promise((ok, no) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
const cache = {};
const once = (k, f) => cache[k] || (cache[k] = f());
const T = Date.now();
const data = () => once("data", () => get("data.json?t=" + T));
const live = () => once("live", () => get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=aud").catch(() => null));
const mkt = () => once("mkt", () => get("market.json?t=" + T).catch(() => null));
const card = () => once("card", () => get("scorecard.json?t=" + T));
const chip = v => '<span class="chip ' + ({ Good: "g", Mixed: "m", Bad: "b" }[v] || "nv") + '">' + esc(v) + "</span>";

// ---------- CAGR (historical calculator, logic from full.html calcRun) ----------
const KEYS = ["BTC", "TSLA", "MSTR", "SEMI"];
let C = null, chart = null;
async function cagr() {
  const el = $("tab-cagr");
  if (!C) {
    el.innerHTML = '<div class="muted">Loading…</div>';
    const [d, cg, , , mk] = await Promise.all([data(), live(), once("chartjs", () => loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js")), once("gc", () => loadScript("growth-calc.js")), mkt()]);
    const lv = cg && cg.bitcoin && cg.bitcoin.aud ? { BTC_AUD: cg.bitcoin.aud, date: new Date().toISOString().slice(0, 10) } : null;
    C = { daily: GrowthCalc.buildDaily(d, lv), yrs: 3, live: !!lv, need: (mk && mk.needed) || null };
    el.innerHTML =
      '<h2>Results</h2><div class="stats" id="cStats"></div><div class="muted" id="cPer"></div>' +
      '<div class="tw"><table><thead><tr><th>Asset</th><th>Put in</th><th>Worth</th><th>Price</th><th>CAGR</th></tr></thead><tbody id="cBody"></tbody></table></div>' +
      '<div class="cbox"><canvas id="cChart" height="230"></canvas></div>' +
      '<h2>Settings</h2><div class="seg" id="cPick">' + KEYS.map(k => '<button data-k="' + k + '">' + k + "</button>").join("") + '<button data-k="mix">Mix</button></div>' +
      '<div class="amts">' + KEYS.map(k => '<label class="am"><input type="checkbox" id="on_' + k + '"' + (k === "SEMI" ? "" : "") + "> " + k + ' <input type="number" inputmode="decimal" min="0" step="100" id="amt_' + k + '" value="2500"></label>').join("") + "</div>" +
      '<div class="row2"><label>Top-up A$ <input type="number" inputmode="decimal" min="0" step="25" id="cTop" value="0"></label><select id="cFreq"><option value="week">weekly</option><option value="month">monthly</option></select></div>' +
      '<div class="seg" id="cYrs"><button data-y="1">1 year</button><button data-y="3" class="on">3 years</button><button data-y="5">5 years</button></div>' +
      '<label class="ck"><input type="checkbox" id="cCrash"> Crash 25% from here</label>';
    KEYS.forEach(k => { $("on_" + k).checked = true; $("on_" + k).onchange = run; $("amt_" + k).oninput = run; });
    $("cTop").oninput = run; $("cFreq").onchange = run; $("cCrash").onchange = run;
    el.querySelectorAll("#cYrs button").forEach(b => b.onclick = () => { C.yrs = +b.dataset.y; el.querySelectorAll("#cYrs button").forEach(x => x.classList.toggle("on", x === b)); run(); });
    el.querySelectorAll("#cPick button").forEach(b => b.onclick = () => {
      const k = b.dataset.k; el.querySelectorAll("#cPick button").forEach(x => x.classList.toggle("on", x === b));
      if (k === "mix") KEYS.forEach(j => $("on_" + j).checked = true);
      else { const tot = KEYS.reduce((a, j) => a + ($("on_" + j).checked ? +$("amt_" + j).value || 0 : 0), 0) || 10000; KEYS.forEach(j => $("on_" + j).checked = j === k); $("amt_" + k).value = tot; }
      run(); });
    el.querySelector('#cPick button[data-k="mix"]').classList.add("on");
  }
  run();
}
function simulate() {
  const D = C.daily, e = D.length - 1, end = D[e].date, ed = new Date(end + "T00:00:00Z");
  const sIso = new Date(Date.UTC(ed.getUTCFullYear() - C.yrs, ed.getUTCMonth(), ed.getUTCDate())).toISOString().slice(0, 10);
  let s = e; while (s > 0 && D[s].date > sIso) s--;
  if (D[s].date > sIso) return { error: "Not enough history for " + C.yrs + " years." };
  const on = KEYS.filter(k => $("on_" + k).checked && (+String($("amt_" + k).value).replace(/[^0-9.]/g, "") || 0) >= 0);
  const amt = {}; on.forEach(k => amt[k] = Math.max(0, +String($("amt_" + k).value).replace(/[^0-9.]/g, "") || 0));
  const dep = on.reduce((a, k) => a + amt[k], 0), top = Math.max(0, +$("cTop").value || 0);
  if (!on.length || (!dep && !top)) return { error: "Tick an asset and enter an amount." };
  const w = {}; on.forEach(k => w[k] = dep ? amt[k] / dep : 1 / on.length);
  const units = {}, put = {}; on.forEach(k => { units[k] = amt[k] / D[s][k]; put[k] = amt[k]; });
  const step = $("cFreq").value === "week" ? 7 : 30.4375, cfs = dep ? [[0, dep]] : [], series = [];
  let putIn = dep;
  for (let i = s; i <= e; i++) {
    const n = i - s;
    if (top > 0 && n > 0 && Math.floor(n / step) > Math.floor((n - 1) / step)) {
      on.forEach(k => { units[k] += top * w[k] / D[i][k]; put[k] += top * w[k]; }); putIn += top; cfs.push([n / 365.25, top]);
    }
    const row = { date: D[i].date, putIn, total: 0 };
    on.forEach(k => { row[k] = units[k] * D[i][k]; row.total += row[k]; });
    series.push(row);
  }
  const Ty = (e - s) / 365.25, crash = $("cCrash").checked, f = crash ? 0.75 : 1, last = series[series.length - 1];
  const endV = last.total * f, fv = r => cfs.reduce((a, [t, c]) => a + c * Math.pow(1 + r, Ty - t), 0);
  let lo = -0.99, hi = 20; for (let j = 0; j < 100; j++) { const m = (lo + hi) / 2; if (fv(m) > endV) hi = m; else lo = m; }
  const rows = on.map(k => ({ k, put: put[k], worth: last[k] * f, chg: D[e][k] / D[s][k] - 1, cagr: Math.pow(D[e][k] / D[s][k], 1 / Ty) - 1 }));
  return { start: D[s].date, end, Ty, on, putIn, endV, todayV: last.total, rate: (lo + hi) / 2, rows, series, crash, top };
}
function run() {
  const r = simulate();
  if (r.error) { $("cBody").innerHTML = ""; $("cPer").textContent = r.error; return; }
  const g = r.endV - r.putIn;
  if (!$("cPutTot")) {
    $("cStats").innerHTML =
      '<div><div class="k" id="cWk"></div><div class="v" id="cWv"></div></div>' +
      '<div><div class="k">Put in (tap to change)</div><div class="v"><span style="display:flex;align-items:center;gap:4px">A$<input type="text" inputmode="decimal" autocomplete="off" id="cPutTot" style="font-size:inherit;font-weight:700;padding:4px 6px"></span><small id="cPutTop"></small></div></div>' +
      '<div><div class="k">Up / Down</div><div class="v" id="cGv"></div></div>' +
      '<div><div class="k">Per year</div><div class="v" id="cRv"></div></div>';
    $("cPutTot").addEventListener("input", e => {
      const el = e.target, c = el.value.replace(/[^0-9.]/g, "").replace(/(\..*)\./g, "$1"); if (c !== el.value) el.value = c;
      const tot = Math.max(0, +c || 0), on = KEYS.filter(k => $("on_" + k).checked); if (!on.length) return;
      const cur = on.map(k => Math.max(0, +String($("amt_" + k).value).replace(/[^0-9.]/g, "") || 0)), sum = cur.reduce((a, b) => a + b, 0);
      on.forEach((k, i) => { $("amt_" + k).value = String(Math.round(tot * (sum ? cur[i] / sum : 1 / on.length) * 100) / 100); });
      $("amt_" + on[0]).dispatchEvent(new Event("input", { bubbles: true }));
      run();
    });
  }

  const start = KEYS.filter(k => $("on_" + k).checked).reduce((a, k) => a + Math.max(0, +String($("amt_" + k).value).replace(/[^0-9.]/g, "") || 0), 0);
  $("cWk").textContent = r.crash ? "Worth after crash" : "Worth now"; $("cWv").textContent = aud(r.endV);
  if (document.activeElement !== $("cPutTot")) $("cPutTot").value = Math.round(start).toLocaleString("en-AU");
  $("cPutTop").textContent = r.top ? "Total incl. top-ups " + aud(r.putIn) : "";
  $("cGv").className = "v " + (g >= 0 ? "up" : "down"); $("cGv").innerHTML = (g >= 0 ? "+" : "") + aud(g) + " <small>(" + pct(g / r.putIn) + ")</small>";
  $("cRv").className = "v " + (r.rate >= 0 ? "up" : "down"); $("cRv").textContent = pct(r.rate);
  $("cPer").textContent = dstr(r.start) + " to " + dstr(r.end) + (r.top ? ", topping up " + aud(r.top) + " " + ($("cFreq").value === "week" ? "weekly" : "monthly") : "") + (r.crash ? ", then −25%" : "") + (C.live ? " · BTC live" : "");
  $("cBody").innerHTML = r.rows.map(x => "<tr><td><b>" + x.k + "</b></td><td>" + aud(x.put) + "</td><td>" + aud(x.worth) + "</td><td>" + cpct(x.chg, 0) + "</td><td>" + cpct(x.cagr) + "</td></tr>").join("") +
    (r.rows.length > 1 ? "<tr class='tot'><td><b>Total</b></td><td>" + aud(r.putIn) + "</td><td><b>" + aud(r.endV) + "</b></td><td>" + cpct(r.endV / r.putIn - 1, 0) + "</td><td>" + cpct(r.rate) + "</td></tr>" : "");
  const col = { BTC: "#f7931a", TSLA: "#e8ecf4", MSTR: "#b388ff", SEMI: "#4dd0e1", total: "#4da3ff" };
  const S = r.series.filter((_, i) => i % 3 === 0 || i === r.series.length - 1), L = S.map(x => x.date);
  const ds = [{ label: "Total", data: S.map(x => Math.round(x.total)), borderColor: col.total, borderWidth: 2.5, pointRadius: 0 },
              { label: "Put in", data: S.map(x => Math.round(x.putIn)), borderColor: "#9aa6bd", borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0 }];
  if (r.on.length > 1) r.on.forEach(k => ds.push({ label: k, data: S.map(x => Math.round(x[k])), borderColor: col[k], borderWidth: 1.2, pointRadius: 0 }));
  if (r.crash) ds.push({ label: "After crash", data: L.map((_, i) => i === L.length - 1 ? Math.round(r.endV) : null), borderColor: "#ff6b6b", backgroundColor: "#ff6b6b", pointRadius: 6, showLine: false });
  if (chart) chart.destroy();
  chart = new Chart($("cChart"), { type: "line", data: { labels: L, datasets: ds },
    options: { animation: false, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: "#e8ecf4", boxWidth: 12 } }, tooltip: { callbacks: { label: c => c.parsed.y == null ? "" : c.dataset.label + ": " + aud(c.parsed.y) } } },
      scales: { x: { ticks: { color: "#9aa6bd", maxTicksLimit: 5, callback: function (v) { return new Date(this.getLabelForValue(v) + "T12:00:00Z").toLocaleDateString("en-AU", { month: "short", year: "2-digit" }); } }, grid: { color: "#222b40" } },
                y: { ticks: { color: "#9aa6bd", callback: v => "A$" + (v / 1000).toFixed(0) + "k" }, grid: { color: "#222b40" } } } } });
}

// ---------- SEMI Scorecard ----------
async function scorecard() {
  const el = $("tab-scorecard"); if (el.dataset.done) return;
  el.innerHTML = '<div class="muted">Loading…</div>';
  const s = await card();
  el.innerHTML = '<h2>SEMI Scorecard</h2><div class="muted">' + esc(s.as_of) + "</div>" +
    (() => { const w = { Good: 0, Mixed: 0, Bad: 0, "Not verified": 0 };
      s.holdings.forEach(h => { const v = parseFloat(String(h.weight)); if (isFinite(v)) w[h.verdict in w ? h.verdict : "Not verified"] += v; });
      const chk = w.Good + w.Mixed + w.Bad, q = chk ? Math.round((w.Good + 0.5 * w.Mixed) / chk * 100) : null;
      const g = q == null ? "Not verified" : q >= 90 ? "Excellent" : q >= 75 ? "Very good" : q >= 60 ? "Good" : q >= 40 ? "Mixed" : "Weak";
      const cl = q == null ? "" : q >= 60 ? "up" : q >= 40 ? "amber" : "down";
      const f = v => v.toFixed(1) + "%";
      return '<div class="ov"><div class="muted">Whole fund quality</div><div class="' + cl + '" style="font-size:26px;font-weight:700">' + g + (q == null ? "" : " · " + q + "/100") + "</div>" +
        '<div class="n">Good ' + f(w.Good) + " · Mixed " + f(w.Mixed) + " · Bad " + f(w.Bad) + " · Not verified " + f(w["Not verified"]) + "</div>" +
        '<div class="muted">Share of fund checked: ' + esc(s.overall.weight) + " · results " + esc(s.overall.dates) + "</div>" +
        '<div class="muted">Grade = Good counts 1, Mixed 0.5, Bad 0, by fund weight, ignoring Not verified. 90+ Excellent, 75-89 Very good, 60-74 Good, 40-59 Mixed, under 40 Weak.</div>' +
        '<div class="n" style="margin-top:6px">' + esc(String(s.overall.flag || "").replace(/^Good .*?Not verified [\d.]+%\.\s*/, "")) + "</div></div>"; })() +
    '<div class="hl">' + s.holdings.map(h => '<div class="h1"><div class="top">' + chip(h.verdict) + " <b>" + esc(h.company) + '</b><span class="wt">' + esc(h.weight) + "</span></div>" +
      '<div class="n">' + esc(h.date) + " · " + esc(h.flag) + ' <span class="muted">(' + esc(h.source) + ")</span></div></div>").join("") + "</div>" +
    (s.watch ? "<h2>What to watch</h2><div class='n'>" + esc(s.watch) + "</div>" : "");
  el.dataset.done = 1;
}

// ---------- Semi Holdings Latest Earnings Scorecard (full SEMI ETF review + live) ----------
const norm = s => String(s).toLowerCase().replace(/[^a-z]/g, "").slice(0, 9);
const tone = t => ({ danger: "b", warning: "m", success: "g", info: "nv" }[t] || "nv");
function block(b) {
  const kids = (b.children || []).map(c => typeof c === "string" ? esc(c) : block(c)).join("");
  switch (b.type) {
    case "Text": return '<p class="n">' + kids + "</p>";
    case "Callout": return '<div class="callout ' + tone(b.tone) + '"><b>' + esc(b.lead) + "</b> " + kids + "</div>";
    case "Rows": return '<div class="rws">' + b.rows.map(r => '<div class="rw"><div>' + (r.lead ? '<span class="muted">' + esc(r.lead) + ": </span>" : "") + "<b>" + esc(r.title) + '</b><div class="n">' + esc(r.detail) + "</div></div>" + (r.status ? '<span class="chip ' + tone(r.status.tone) + '">' + esc(r.status.label) + "</span>" : "") + "</div>").join("") + "</div>";
    case "Properties": return '<div class="tw"><table>' + b.items.map(i => "<tr><th>" + esc(i.label) + "</th><td>" + esc(i.value) + "</td></tr>").join("") + "</table></div>";
    case "Bars": { const m = Math.max(...b.bars.map(x => Math.abs(x.value))); return '<div class="bars">' + b.bars.map(x => '<div class="bar"><span class="bl">' + esc(x.label) + '</span><span class="bt"><i class="' + (x.value < 0 ? "neg" : "") + '" style="width:' + (Math.abs(x.value) / m * 100).toFixed(1) + '%"></i></span><span class="bv">' + esc(x.display) + "</span></div>").join("") + "</div>"; }
    case "Table": return '<div class="tw"><table><thead><tr>' + b.columns.map(c => "<th>" + esc(c) + "</th>").join("") + "</tr></thead><tbody>" + b.rows.map(r => "<tr>" + r.map(c => "<td>" + esc(c) + "</td>").join("") + "</tr>").join("") + "</tbody></table></div>";
    case "NumberedList": return '<ol class="n">' + b.items.map(i => "<li>" + esc(i) + "</li>").join("") + "</ol>";
    case "Metrics": return '<div class="stats">' + b.metrics.map(x => '<div><div class="k">' + esc(x.label) + '</div><div class="v">' + esc(x.value) + '</div><div class="muted">' + esc(x.detail) + "</div></div>").join("") + "</div>";
    case "ProsCons": return '<div class="pc"><div><b class="up">' + esc(b.prosHeading) + '</b><ul class="n">' + b.pros.map(i => "<li>" + esc(i) + "</li>").join("") + '</ul></div><div><b class="down">' + esc(b.consHeading) + '</b><ul class="n">' + b.cons.map(i => "<li>" + esc(i) + "</li>").join("") + "</ul></div></div>";
    case "LinkCards": return '<ul class="n links">' + b.links.map(l => '<li><a href="' + esc(l.href) + '" target="_blank" rel="noopener">' + esc(l.title) + '</a> <span class="muted">' + esc(l.site) + "</span></li>").join("") + "</ul>";
    default: return kids;
  }
}
async function review() {
  const el = $("tab-semireview"); if (el.dataset.done) return;
  el.innerHTML = '<div class="muted">Loading…</div>';
  const [d, s, rv, hp] = await Promise.all([data(), card(), get("semireview.json?t=" + T), get("holdings.json?t=" + T).catch(() => null)]);
  const sig = d.semi_signals, td = d.today.SEMI;
  const revRows = {}; const hs = rv.sections.find(x => x.heading === "Holdings");
  (hs.blocks.find(b => b.type === "Table").rows).forEach(r => revRows[norm(r[0])] = r);
  const HP = (hp && hp.holdings) || {};
  const px = h => { const p = HP[h.company]; return p && p.close != null ? p.close.toLocaleString("en-AU", { maximumFractionDigits: 2 }) + " " + esc(p.currency) + " " + cpct(p.change) : ""; };
  let html = "<h2>Semi Holdings Latest Earnings Scorecard</h2>" +
    '<div class="stats">' +
    '<div><div class="k">SEMI (ASX)</div><div class="v">A$' + td.close.toFixed(2) + " " + cpct(td.change) + '</div><div class="muted">' + dstr(td.date) + " close</div></div>" +
    '<div><div class="k">vs 50-day</div><div class="v">' + cpct(sig.vs_sma50) + '</div><div class="muted">A$' + sig.sma50.toFixed(2) + "</div></div>" +
    '<div><div class="k">vs 200-day</div><div class="v">' + cpct(sig.vs_sma200) + '</div><div class="muted">A$' + sig.sma200.toFixed(2) + "</div></div>" +
    '<div><div class="k">Weekly RSI</div><div class="v">' + sig.weekly_rsi.toFixed(0) + '</div><div class="muted">From 52w high ' + pct(sig.from_high_52w) + "</div></div></div>" +
    '<div class="ov"><b>Earnings: ' + esc(s.overall.verdict) + '</b><div class="n">' + esc(s.overall.flag) + '</div><div class="muted">' + esc(s.as_of) + "</div></div>" +
    '<h2>Holdings</h2><div class="muted">Tap a holding for details. Prices: last close' + (hp ? ", saved " + new Date(hp.generated_utc).toLocaleString("en-AU", { timeZone: "Australia/Melbourne", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) + " AEDT" : " unavailable") + ".</div><div class='hl'>" +
    s.holdings.map(h => { const r = revRows[norm(h.company)] || [], p = HP[h.company] || {};
      return '<details class="h1"><summary><div class="top">' + chip(h.verdict) + " <b>" + esc(h.company) + '</b><span class="wt">' + esc(h.weight) + '</span></div><div class="muted">' + px(h) + "</div></summary>" +
        '<div class="dd"><div><span class="muted">Latest results:</span> ' + esc(h.date) + " · " + esc(h.verdict) + "</div><div>" + esc(h.flag) + "</div>" +
        (r[2] ? '<div><b class="up">Positive</b> ' + esc(r[2]) + "</div>" : "") + (r[3] ? '<div><b class="down">Negative</b> ' + esc(r[3]) + "</div>" : "") +
        (p.close != null ? '<div><span class="muted">Price:</span> ' + px(h) + " · " + esc(p.ticker) + " · " + dstr(p.date) + " close</div>" : "") +
        '<div class="muted">Source: ' + esc(h.source) + " · positives/negatives from the review, as of 30 Oct 2026</div></div></details>"; }).join("") + "</div>" +
    '<h2>Full SEMI ETF review</h2><div class="muted">' + esc(rv.as_of) + '</div><p class="n">' + esc(rv.summary) + "</p>";
  for (const sec of rv.sections) {
    html += "<h3>" + esc(sec.heading) + "</h3>";
    if (sec.heading === "Holdings") { html += '<p class="n muted">All 30 holdings with positives and negatives are in the tappable list above.</p>' + sec.blocks.filter(b => b.type !== "Table").map(block).join(""); continue; }
    if (sec.heading === "Performance so far") {
      const ser = d.series.SEMI, last = ser[ser.length - 1];
      const cg = y => { const t = new Date(last[0]); t.setFullYear(t.getFullYear() - y); const iso = t.toISOString().slice(0, 10); const f = ser.find(x => x[0] >= iso); return f ? Math.pow(last[1] / f[1], 1 / y) - 1 : null; };
      html += '<div class="muted">Live (adjusted ASX close, to ' + dstr(last[0]) + "): 1y " + pct(cg(1)) + " · 3y " + pct(cg(3)) + " p.a. · since 2021 " + pct(Math.pow(last[1] / ser[0][1], 1 / ((Date.parse(last[0]) - Date.parse(ser[0][0])) / 3.15576e10)) - 1) + " p.a.</div>";
    }
    html += sec.blocks.map(block).join("");
  }
  html += '<div class="muted">Original page: <a href="' + esc(rv.source_page) + '" target="_blank" rel="noopener">SEMI ETF review</a></div>';
  el.innerHTML = html; el.dataset.done = 1;
}
// ---------- Chips (Micron, SK hynix, Broadcom, TSMC) — same maths as CAGR, data from chips.json ----------
const XK = ["MU", "HYNIX", "AVGO", "TSM", "SEMI"], XN = { MU: "Micron", HYNIX: "SK hynix", AVGO: "Broadcom", TSM: "TSMC", SEMI: "SEMI" };
const XCOL = { MU: "#4dd0e1", HYNIX: "#f7931a", AVGO: "#ff6b9a", TSM: "#b388ff", SEMI: "#ffd84d", total: "#4da3ff" };
const XKEY = "hubChipsAmts3", num = v => Math.max(0, +String(v == null ? "" : v).replace(/[^0-9.]/g, "") || 0);
let X = null, xchart = null;
const eff = k => num($("xamt_" + k).value), wmul = k => num($("xwm_" + k).value);
const xsave = () => { const o = {}; XK.forEach(k => { o["xamt_" + k] = $("xamt_" + k).value; o["xwm_" + k] = $("xwm_" + k).value; o["xon_" + k] = $("xon_" + k).checked; }); o.xTop = $("xTop").value; o.xFreq = $("xFreq").value; try { localStorage.setItem(XKEY, JSON.stringify(o)); } catch (_) {} };
const clean = el => { const c = el.value.replace(/[^0-9.]/g, "").replace(/(\..*)\./g, "$1"); if (c !== el.value) el.value = c; };
async function chips() {
  const el = $("tab-chips");
  if (!X) {
    el.innerHTML = '<div class="muted">Loading…</div>';
    const [d, dd] = await Promise.all([get("chips.json?t=" + T), data().catch(() => null), once("chartjs", () => loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"))]);
    const D = d.dates.map((dt, i) => { const r = { date: dt }; XK.forEach(k => { if (d.aud[k]) r[k] = d.aud[k][i]; }); return r; });
    if (dd && dd.series && dd.series.SEMI) { const m = new Map(dd.series.SEMI); let cur = null; for (const [dt, v] of dd.series.SEMI) { if (dt <= D[0].date) cur = v; else break; } D.forEach(r => { if (m.has(r.date)) cur = m.get(r.date); r.SEMI = cur; }); }
    X = { daily: D, yrs: 3 };
    let saved = {}; try { saved = JSON.parse(localStorage.getItem(XKEY) || "{}"); } catch (_) {}
    const inp = (id, v) => '<input type="text" inputmode="decimal" autocomplete="off" id="' + id + '" value="' + esc(v) + '">';
    el.innerHTML =
      '<h2>Chips: Micron, SK hynix, Broadcom, TSMC + SEMI</h2>' +
      '<h2>Results</h2><div class="stats" id="xStats"></div><div class="muted" id="xPer"></div>' +
      '<div class="tw"><table><thead><tr><th>Asset</th><th>Put in</th><th>Worth</th><th>Price</th><th>CAGR</th></tr></thead><tbody id="xBody"></tbody></table></div>' +
      '<div class="ov" id="xSemi"></div>' +
      '<h2>What if</h2><div class="tw"><table class="xw"><thead><tr><th>Asset</th><th>Deposit</th><th>Multiple</th><th>Would be worth</th></tr></thead><tbody>' +
      XK.map(k => '<tr id="xwr_' + k + '"><td><b>' + XN[k] + '</b></td><td id="xwd_' + k + '"></td><td><span class="xwi">' + inp("xwm_" + k, saved["xwm_" + k] != null ? saved["xwm_" + k] : "1") + '<span>×</span></span></td><td id="xww_' + k + '"></td></tr>').join("") +
      '<tr class="tot"><td><b>Total</b></td><td id="xwdT"></td><td id="xwmT"></td><td id="xwwT"></td></tr></tbody></table></div>' +
      '<div class="muted">What if each deposit ended up worth that many times over (type 3, 4, 5… or 3x). Would be worth = deposit × multiple. A what-if, not a forecast.</div>' +
      '<div class="cbox"><canvas id="xChart"></canvas></div>' +
      '<h2>Settings</h2><div class="seg" id="xPick">' + XK.map(k => '<button data-k="' + k + '">' + XN[k] + "</button>").join("") + '<button data-k="mix">Mix</button></div>' +
      '<div class="amts">' + XK.map(k => '<label class="am"><input type="checkbox" id="xon_' + k + '"> <span class="xn">' + XN[k] + '</span><span class="xa">A$' + inp("xamt_" + k, saved["xamt_" + k] != null ? saved["xamt_" + k] : "5000") + "</span></label>").join("") + "</div>" +
      '<div class="row2"><label>Top-up A$ ' + inp("xTop", saved.xTop != null ? saved.xTop : "0") + '</label><select id="xFreq"><option value="week">weekly</option><option value="month">monthly</option></select></div>' +
      '<div class="seg" id="xYrs"><button data-y="1">1 year</button><button data-y="2">2 years</button><button data-y="3" class="on">3 years</button><button data-y="4">4 years</button><button data-y="5">5 years</button></div>' +
      '<label class="ck"><input type="checkbox" id="xCrash"> Crash 25% from here</label>' +
      '<div class="muted" style="margin-top:10px">All in A$. Prices: Yahoo Finance adjusted daily closes (dividends reinvested) — Micron MU (US$), SK hynix 000660.KS (Korea, KRW), Broadcom AVGO (US$), TSMC TSM (US ADR, US$), SEMI SEMI.AX (Global X, ASX, A$) — US$ and KRW converted with each day\'s AUDUSD / AUDKRW rate. Prices to ' + dstr(d.dates[d.dates.length - 1]) + '. SK hynix uses its Korean listing because its US ticker SKHY only started on 10 Jul 2026. Past returns, general information only.</div>';
    if (saved.xFreq) $("xFreq").value = saved.xFreq;
    XK.forEach(k => { $("xon_" + k).checked = saved["xon_" + k] != null ? !!saved["xon_" + k] : k !== "SEMI";
      $("xon_" + k).onchange = () => { xsave(); xrun(); }; $("xamt_" + k).oninput = e => { clean(e.target); xsave(); xrun(); }; $("xwm_" + k).oninput = e => { clean(e.target); xsave(); xwhat(); }; });
    $("xTop").oninput = e => { clean(e.target); xsave(); xrun(); }; $("xFreq").onchange = () => { xsave(); xrun(); }; $("xCrash").onchange = xrun;
    el.querySelectorAll("#xYrs button").forEach(b => b.onclick = () => { X.yrs = +b.dataset.y; el.querySelectorAll("#xYrs button").forEach(x => x.classList.toggle("on", x === b)); xrun(); });
    el.querySelectorAll("#xPick button").forEach(b => b.onclick = () => {
      const k = b.dataset.k; el.querySelectorAll("#xPick button").forEach(x => x.classList.toggle("on", x === b));
      if (k === "mix") XK.forEach(j => $("xon_" + j).checked = true);
      else { const tot = XK.reduce((a, j) => a + ($("xon_" + j).checked ? eff(j) : 0), 0) || 20000; XK.forEach(j => $("xon_" + j).checked = j === k); $("xamt_" + k).value = String(tot); }
      xsave(); xrun(); });
    const allOn = XK.every(k => $("xon_" + k).checked), only = XK.filter(k => $("xon_" + k).checked);
    el.querySelector('#xPick button[data-k="' + (allOn || only.length !== 1 ? "mix" : only[0]) + '"]').classList.add("on");
  }
  xrun();
}
function xsim() {
  const D = X.daily, e = D.length - 1, end = D[e].date, ed = new Date(end + "T00:00:00Z");
  const sIso = new Date(Date.UTC(ed.getUTCFullYear() - X.yrs, ed.getUTCMonth(), ed.getUTCDate())).toISOString().slice(0, 10);
  let s = e; while (s > 0 && D[s].date > sIso) s--;
  if (D[s].date > sIso) return { error: "Not enough history for " + X.yrs + " years." };
  const on = XK.filter(k => $("xon_" + k).checked);
  if (on.some(k => !(D[s][k] > 0))) return { error: "No SEMI price history for that start date (SEMI data didn't load or starts later)." };
  const amt = {}; on.forEach(k => amt[k] = eff(k));
  const dep = on.reduce((a, k) => a + amt[k], 0), top = num($("xTop").value);
  if (!on.length || (!dep && !top)) return { error: "Tick a stock and enter an amount." };
  const w = {}; on.forEach(k => w[k] = dep ? amt[k] / dep : 1 / on.length);
  const units = {}, put = {}; on.forEach(k => { units[k] = amt[k] / D[s][k]; put[k] = amt[k]; });
  const step = $("xFreq").value === "week" ? 7 : 30.4375, cfs = dep ? [[0, dep]] : [], series = [];
  let putIn = dep;
  for (let i = s; i <= e; i++) {
    const n = i - s;
    if (top > 0 && n > 0 && Math.floor(n / step) > Math.floor((n - 1) / step)) {
      on.forEach(k => { units[k] += top * w[k] / D[i][k]; put[k] += top * w[k]; }); putIn += top; cfs.push([n / 365.25, top]);
    }
    const row = { date: D[i].date, putIn, total: 0 };
    on.forEach(k => { row[k] = units[k] * D[i][k]; row.total += row[k]; });
    series.push(row);
  }
  const Ty = (e - s) / 365.25, crash = $("xCrash").checked, f = crash ? 0.75 : 1, last = series[series.length - 1];
  const endV = last.total * f, fv = r => cfs.reduce((a, [t, c]) => a + c * Math.pow(1 + r, Ty - t), 0);
  let lo = -0.99, hi = 20; for (let j = 0; j < 100; j++) { const m = (lo + hi) / 2; if (fv(m) > endV) hi = m; else lo = m; }
  const rows = on.map(k => ({ k, put: put[k], worth: last[k] * f, chg: D[e][k] / D[s][k] - 1, cagr: Math.pow(D[e][k] / D[s][k], 1 / Ty) - 1 }));
  let semi = null;
  if (D[s].SEMI > 0) { let u = dep / D[s].SEMI; for (let i = s; i <= e; i++) { const n = i - s; if (top > 0 && n > 0 && Math.floor(n / step) > Math.floor((n - 1) / step)) u += top / D[i].SEMI; series[i - s].SEMIALL = u * D[i].SEMI; }
    const sv = u * D[e].SEMI * f; let a = -0.99, b = 20; for (let j = 0; j < 100; j++) { const m = (a + b) / 2; if (fv(m) > sv) b = m; else a = m; }
    semi = { worth: sv, chg: D[e].SEMI / D[s].SEMI - 1, cagr: Math.pow(D[e].SEMI / D[s].SEMI, 1 / Ty) - 1, rate: (a + b) / 2 }; }
  return { start: D[s].date, end, Ty, on, putIn, endV, rate: (lo + hi) / 2, rows, series, crash, top, semi };
}
function xwhat() {
  let d = 0, w = 0;
  XK.forEach(k => { const on = $("xon_" + k).checked; $("xwr_" + k).hidden = !on; if (!on) return;
    const dep = eff(k), m = $("xwm_" + k).value.trim() === "" ? 1 : wmul(k), v = dep * m; d += dep; w += v;
    $("xwd_" + k).textContent = aud(dep); $("xww_" + k).textContent = aud(v); });
  $("xwdT").textContent = aud(d); $("xwwT").innerHTML = "<b>" + aud(w) + "</b>"; $("xwmT").textContent = d ? (Math.round(w / d * 100) / 100) + "×" : "–";
}
function xrun() {
  xwhat();
  const r = xsim();
  if (r.error) { $("xBody").innerHTML = ""; $("xPer").textContent = r.error; return; }
  const g = r.endV - r.putIn;
  if (!$("xPutTot")) {
    $("xStats").innerHTML =
      '<div><div class="k" id="xWk"></div><div class="v" id="xWv"></div></div>' +
      '<div><div class="k">Put in (tap to change)</div><div class="v"><span style="display:flex;align-items:center;gap:4px">A$<input type="text" inputmode="decimal" autocomplete="off" id="xPutTot"></span><small id="xPutTop"></small></div></div>' +
      '<div><div class="k">Up / Down</div><div class="v" id="xGv"></div></div>' +
      '<div><div class="k">Per year</div><div class="v" id="xRv"></div></div>';
    $("xPutTot").addEventListener("input", e => {
      clean(e.target); const tot = num(e.target.value), on = XK.filter(k => $("xon_" + k).checked); if (!on.length) return;
      const cur = on.map(k => eff(k)), sum = cur.reduce((a, b) => a + b, 0);
      on.forEach((k, i) => { $("xamt_" + k).value = String(Math.round(tot * (sum ? cur[i] / sum : 1 / on.length) * 100) / 100); });
      xsave(); xrun();
    });
  }
  const start = XK.filter(k => $("xon_" + k).checked).reduce((a, k) => a + eff(k), 0);
  $("xWk").textContent = r.crash ? "Worth after crash" : "Worth now"; $("xWv").textContent = aud(r.endV);
  if (document.activeElement !== $("xPutTot")) $("xPutTot").value = Math.round(start).toLocaleString("en-AU");
  $("xPutTop").textContent = r.top ? "Total incl. top-ups " + aud(r.putIn) : "";
  $("xGv").className = "v " + (g >= 0 ? "up" : "down"); $("xGv").innerHTML = (g >= 0 ? "+" : "") + aud(g) + " <small>(" + pct(g / r.putIn) + ")</small>";
  $("xRv").className = "v " + (r.rate >= 0 ? "up" : "down"); $("xRv").textContent = pct(r.rate);
  $("xPer").textContent = dstr(r.start) + " to " + dstr(r.end) + (r.top ? ", topping up " + aud(r.top) + " " + ($("xFreq").value === "week" ? "weekly" : "monthly") : "") + (r.crash ? ", then −25%" : "");
  $("xBody").innerHTML = r.rows.map(x => "<tr><td><b>" + XN[x.k] + "</b></td><td>" + aud(x.put) + "</td><td>" + aud(x.worth) + "</td><td>" + cpct(x.chg, 0) + "</td><td>" + cpct(x.cagr) + "</td></tr>").join("") +
    (r.rows.length > 1 ? "<tr class='tot'><td><b>Total</b></td><td>" + aud(r.putIn) + "</td><td><b>" + aud(r.endV) + "</b></td><td>" + cpct(r.endV / r.putIn - 1, 0) + "</td><td>" + cpct(r.rate) + "</td></tr>" : "");
  $("xSemi").innerHTML = r.semi ? "<b>Same total money all in SEMI (Global X, ASX) instead:</b> worth " + aud(r.semi.worth) + " (" + cpct(r.semi.worth / r.putIn - 1, 0) + "), SEMI price " + cpct(r.semi.chg, 0) + ", CAGR " + cpct(r.semi.cagr) + ", per year " + cpct(r.semi.rate) + ". Your mix " + (r.endV >= r.semi.worth ? "ahead by " + aud(r.endV - r.semi.worth) : "behind by " + aud(r.semi.worth - r.endV)) + "." : '<span class="muted">SEMI comparison unavailable.</span>';
  const S = r.series.filter((_, i) => i % 3 === 0 || i === r.series.length - 1), L = S.map(x => x.date);
  const ds = [{ label: "Total", data: S.map(x => Math.round(x.total)), borderColor: XCOL.total, borderWidth: 2.5, pointRadius: 0 },
              { label: "Put in", data: S.map(x => Math.round(x.putIn)), borderColor: "#9aa6bd", borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0 }];
  if (r.semi) ds.push({ label: "All in SEMI (same money)", data: S.map(x => Math.round(x.SEMIALL)), borderColor: "#7ee2a0", borderDash: [2, 3], borderWidth: 2, pointRadius: 0 });
  if (r.on.length > 1) r.on.forEach(k => ds.push({ label: XN[k], data: S.map(x => Math.round(x[k])), borderColor: XCOL[k], borderWidth: 1.2, pointRadius: 0 }));
  if (r.crash) ds.push({ label: "After crash", data: L.map((_, i) => i === L.length - 1 ? Math.round(r.endV) : null), borderColor: "#ff6b6b", backgroundColor: "#ff6b6b", pointRadius: 6, showLine: false });
  if (xchart) xchart.destroy();
  const big = innerWidth > 700 ? 17 : 13;
  xchart = new Chart($("xChart"), { type: "line", data: { labels: L, datasets: ds },
    options: { animation: false, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: "#e8ecf4", boxWidth: 14, font: { size: big } } }, tooltip: { callbacks: { label: c => c.parsed.y == null ? "" : c.dataset.label + ": " + aud(c.parsed.y) } } },
      scales: { x: { ticks: { color: "#9aa6bd", maxTicksLimit: 6, font: { size: big }, callback: function (v) { return new Date(this.getLabelForValue(v) + "T12:00:00Z").toLocaleDateString("en-AU", { month: "short", year: "2-digit" }); } }, grid: { color: "#222b40" } },
                y: { ticks: { color: "#9aa6bd", font: { size: big }, callback: v => "A$" + (v / 1000).toFixed(0) + "k" }, grid: { color: "#222b40" } } } } });
}
const NAMES = { TSLA: "Tesla", BTC: "Bitcoin", MSTR: "MSTR" };
function assetScore(k) {
  return async () => {
    const el = $("tab-" + k.toLowerCase() + "-score");
    const mk = await mkt(); const x = mk && mk.scores && mk.scores[k];
    if (!x) { el.innerHTML = '<div class="muted">No score yet.</div>'; return; }
    const P = x.points || {}, R = x.reasons || {}, g = x.growth_detail || {}, c = g.currency || "";
    const st = { "On track": "up", Mixed: "amber", Behind: "down" }[x.status] || "";
    const G = P.trend >= 3 ? ["On track", "up"] : P.trend == 2 ? ["Mixed", "amber"] : ["Behind", "down"];
    const n = v => c + Number(v).toLocaleString("en-AU", { maximumFractionDigits: 2 });
    const ab = (p, a) => (p > a ? "above" : "below");
    const num = g.price != null ? "<div class='gd'>Price " + n(g.price) + (g.price_date ? " (" + dstr(g.price_date) + ")" : "") + " · 50-day avg " + n(g.ma50) + " (" + ab(g.price, g.ma50) + ") · 200-day avg " + n(g.ma200) + " (" + ab(g.price, g.ma200) + ") · weekly RSI " + g.rsi_week + (g.rsi_week >= 35 && g.rsi_week <= 70 ? " (in 35-70)" : " (outside 35-70)") + "</div>" : "";
    const row = (lab, p, mx, r, extra) => "<tr><td><b>" + lab + "</b><br>" + p + "/" + mx + "</td><td>" + esc(r) + (extra || "") + "</td></tr>";
    el.innerHTML = "<h2>" + NAMES[k] + " Scorecard</h2>" +
      "<div class='box'><div style='font-size:28px;font-weight:700'>" + "<span class='" + st + "' title='" + esc(x.status) + "'>" + x.score + "/10</span>" + "</div>" +
      "<div class='" + G[1] + "' style='font-weight:600;margin-top:4px'>Growth: " + G[0] + "</div>" +
      (x.as_of ? "<div class='muted' style='margin-top:4px'>As of " + dstr(x.as_of) + "</div>" : "") + "</div>" +
      "<table class='parts'><thead><tr><th>Part</th><th>Why</th></tr></thead><tbody>" +
      row("Fundamentals", P.fundamentals, 4, R.fundamentals) + row("News", P.news, 3, R.news) + row("Growth", P.trend, 3, R.growth, num) + "</tbody></table>" +
      "<h3>Sources</h3><ul class='src'>" + (x.sources || []).map(s => "<li><a href='" + esc(s.url) + "' target='_blank' rel='noopener'>" + esc(s.label) + "</a></li>").join("") + "</ul>" +
      "<p class='muted'>How it's scored: Fundamentals 0-4 + News 0-3 + Growth (price trend) 0-3. Growth gets 1 point each for price above its 50-day average, above its 200-day average, and weekly RSI between 35 and 70. Overall: 7-10 On track, 6 Mixed, 0-5 Behind. No price targets. General information only, not advice.</p>";
  };
}
window.HubTabs = { cagr, chips, scorecard, semireview: review, "tsla-score": assetScore("TSLA"), "btc-score": assetScore("BTC"), "mstr-score": assetScore("MSTR") };
})();
