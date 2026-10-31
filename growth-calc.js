// Basket growth maths. Works in the browser (window.GrowthCalc) and in Node (module.exports).
(function (root) {
  const HOLDINGS = [
    { key: "BTC",  name: "Bitcoin",                   weight: 0.35, usd: true  },
    { key: "TSLA", name: "Tesla (TSLA)",              weight: 0.30, usd: true  },
    { key: "SEMI", name: "Global X Semiconductor (SEMI.AX)", weight: 0.25, usd: false },
    { key: "MSTR", name: "Strategy (MSTR)",           weight: 0.10, usd: true  },
  ];
  const OPTIONS = {
    all:  { label: "All four", weights: { BTC: 0.35, TSLA: 0.30, SEMI: 0.25, MSTR: 0.10 } },
    tsla: { label: "Tesla (TSLA)", weights: { TSLA: 1 } },
    mstr: { label: "Strategy (MSTR)", weights: { MSTR: 1 } },
    btc:  { label: "Bitcoin (BTC)", weights: { BTC: 1 } },
    semi: { label: "SEMI", weights: { SEMI: 1 } },
  };
  const DAY = 86400000;
  const iso = d => new Date(d).toISOString().slice(0, 10);

  // Build a day-by-day table of AUD prices (every calendar day, gaps carried forward).
  // live: optional { BTC_AUD: number, date: "YYYY-MM-DD" } to set the latest Bitcoin price.
  function buildDaily(data, live) {
    const maps = {}, first = {};
    for (const k of ["BTC", "TSLA", "MSTR", "SEMI", "AUDUSD"]) {
      maps[k] = new Map(data.series[k]);
      first[k] = data.series[k][0][0];
    }
    let last = "0000";
    for (const k in maps) { const s = data.series[k]; if (s[s.length - 1][0] > last) last = s[s.length - 1][0]; }
    if (live && live.date && live.date > last) last = live.date;
    const start = ["BTC", "TSLA", "MSTR", "SEMI", "AUDUSD"].map(k => first[k]).sort().pop();
    const out = []; const cur = {};
    // seed carry-forward values from before the common start
    for (const k in maps) for (const [d, v] of data.series[k]) { if (d <= start) cur[k] = v; else break; }
    for (let t = Date.parse(start + "T00:00:00Z"); iso(t) <= last; t += DAY) {
      const d = iso(t);
      for (const k in maps) if (maps[k].has(d)) cur[k] = maps[k].get(d);
      const fx = cur.AUDUSD;
      const row = { date: d, BTC: cur.BTC / fx, TSLA: cur.TSLA / fx, MSTR: cur.MSTR / fx, SEMI: cur.SEMI };
      out.push(row);
    }
    if (live && live.BTC_AUD && out.length) out[out.length - 1].BTC = live.BTC_AUD;
    return out;
  }

  // years: 1, 3 or 5. endDate optional (defaults to the latest day).
  function compute(daily, optKey, years, deposit, endDate) {
    let endIdx = daily.length - 1;
    if (endDate) while (endIdx > 0 && daily[endIdx].date > endDate) endIdx--;
    const end = daily[endIdx];
    const e = new Date(end.date + "T00:00:00Z");
    const s = new Date(Date.UTC(e.getUTCFullYear() - years, e.getUTCMonth(), e.getUTCDate()));
    const sIso = iso(s);
    let startIdx = endIdx;
    while (startIdx > 0 && daily[startIdx].date > sIso) startIdx--;
    if (daily[startIdx].date > sIso) return { error: "Not enough history for " + years + " years." };
    const start = daily[startIdx];
    const yrs = (Date.parse(end.date) - Date.parse(start.date)) / (365.25 * DAY);
    const w = OPTIONS[optKey].weights;
    const units = {};
    for (const k in w) units[k] = (deposit * w[k]) / start[k];
    const series = [];
    for (let i = startIdx; i <= endIdx; i++) {
      let v = 0; for (const k in units) v += units[k] * daily[i][k];
      series.push({ date: daily[i].date, value: v });
    }
    const valueNow = series[series.length - 1].value;
    const cagr = Math.pow(valueNow / deposit, 1 / yrs) - 1;
    const holdings = HOLDINGS.map(h => {
      const p0 = start[h.key], p1 = end[h.key];
      return { key: h.key, name: h.name, weight: w[h.key] || 0, inBasket: !!w[h.key],
               startPrice: p0, endPrice: p1, change: p1 / p0 - 1, cagr: Math.pow(p1 / p0, 1 / yrs) - 1,
               valueNow: w[h.key] ? units[h.key] * p1 : 0 };
    });
    return { startDate: start.date, endDate: end.date, years: yrs, deposit, valueNow,
             totalChange: valueNow / deposit - 1, cagr, series, holdings };
  }

  const api = { HOLDINGS, OPTIONS, buildDaily, compute };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.GrowthCalc = api;
})(typeof window !== "undefined" ? window : globalThis);
