"""Chips backtest: Portfolio A (A$5k each MU, 000660.KS, AVGO, TSM, buy-and-hold) vs Portfolio B (A$20k SEMI.AX).
Reproducible: /workspace/yfv/bin/python /workspace/chips_backtest.py
Writes /workspace/growth-site/chips_backtest.json and raw downloads to /workspace/backtest_raw/.
Data: Yahoo Finance via yfinance (Adj Close = split + dividend adjusted), RBA cash rate target decisions (rba.gov.au).
"""
import json, math, re, os, datetime as dt, warnings, urllib.request
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf

OUT = "/workspace/growth-site/chips_backtest.json"
RAW = "/workspace/backtest_raw"
STOCKS = {"MU": ("MU", "USD", "Micron"), "HYNIX": ("000660.KS", "KRW", "SK hynix"),
          "AVGO": ("AVGO", "USD", "Broadcom"), "TSM": ("TSM", "USD", "TSMC (ADR)")}
ETF = {"SEMI": ("SEMI.AX", "AUD", "Global X Semiconductor ETF (ASX: SEMI)")}
FXT = {"USD": "AUDUSD=X", "KRW": "AUDKRW=X"}
PERIODS = {"3y": ("2023-11-01", "2026-10-30"), "2y": ("2024-11-01", "2026-10-30")}
INIT_EACH, INIT_TOTAL = 5000.0, 20000.0
ANN = 252


def dl(sym):
    h = yf.Ticker(sym).history(start="2022-10-01", end="2026-11-01", auto_adjust=False, actions=True)
    if h.empty:
        raise SystemExit("no data " + sym)
    h.index = pd.to_datetime([i.strftime("%Y-%m-%d") for i in h.index])
    h = h[~h.index.duplicated(keep="last")]
    h.to_csv(f"{RAW}/{sym.replace('=', '_')}.csv")
    return h


def rba_cash_rate():
    url = "https://www.rba.gov.au/statistics/cash-rate/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    open(f"{RAW}/rba_cash_rate.html", "w").write(html)
    rows = re.findall(r'<th scope="row">([^<]+)</th>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>', html)
    out = sorted((pd.Timestamp(dt.datetime.strptime(d.strip(), "%d %b %Y")), float(r)) for d, _, r in rows if re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", r))
    if not out:
        raise SystemExit("RBA table parse failed")
    return pd.Series([r for _, r in out], index=[d for d, _ in out])


def avg_rate(cr, s, e):
    days = pd.date_range(s, e, freq="D")
    daily = cr.reindex(cr.index.union(days)).ffill().reindex(days)
    return float(daily.mean()) / 100, daily


def last_on_or_before(s, d):
    sub = s[s.index <= d].dropna()
    return (sub.index[-1], float(sub.iloc[-1])) if len(sub) else (None, None)


def first_on_or_after(s, d):
    sub = s[s.index >= d].dropna()
    return (sub.index[0], float(sub.iloc[0])) if len(sub) else (None, None)


def own_tr(h, s, e):
    """Total-return index built from split-adjusted Close + cash dividends reinvested at the ex-date close."""
    c, dv = h["Close"], h["Dividends"].fillna(0)
    sub = h[(h.index >= s) & (h.index <= e)]
    tr = 1.0
    for i in range(1, len(sub)):
        tr *= (sub["Close"].iloc[i] + sub["Dividends"].iloc[i]) / sub["Close"].iloc[i - 1]
    return tr - 1, float(sub["Close"].iloc[-1] / sub["Close"].iloc[0] - 1), float(sub["Dividends"].iloc[1:].sum())


def metrics(v, rf, start, end):
    """v: daily A$ value series on the metrics calendar (first point = start)."""
    r = v.pct_change().dropna()
    days = (end - start).days
    cagr = (v.iloc[-1] / v.iloc[0]) ** (365.25 / days) - 1
    vol = float(r.std(ddof=1) * math.sqrt(ANN))
    rfd = rf / ANN
    dd_dev = float(math.sqrt(np.mean(np.minimum(r - rfd, 0) ** 2)) * math.sqrt(ANN))
    peak = v.cummax(); dd = v / peak - 1
    t = dd.idxmin(); p = v[:t].idxmax()
    rec = v[(v.index > t) & (v >= v[p])]
    roll = []
    for d in v.index:
        b = d - pd.Timedelta(days=365)
        if b < v.index[0]:
            continue
        bd, bv = last_on_or_before(v, b)
        roll.append((d, bd, v[d] / bv - 1))
    worst = min(roll, key=lambda x: x[2]) if roll else None
    best = max(roll, key=lambda x: x[2]) if roll else None
    cal = {}
    for y in (2024, 2025):
        y0, y1 = pd.Timestamp(f"{y-1}-12-31"), pd.Timestamp(f"{y}-12-31")
        if v.index[0] <= pd.Timestamp(f"{y}-01-01") - pd.Timedelta(days=1) or v.index[0] <= y0:
            if v.index[0] <= y0 and v.index[-1] >= y1:
                d0, a = last_on_or_before(v, y0); d1, b2 = last_on_or_before(v, y1)
                cal[str(y)] = {"return": b2 / a - 1, "from": d0.strftime("%Y-%m-%d"), "to": d1.strftime("%Y-%m-%d")}
    return {"start_value": float(v.iloc[0]), "final_value": float(v.iloc[-1]), "total_return": float(v.iloc[-1] / v.iloc[0] - 1),
            "days": days, "cagr": float(cagr), "vol": vol, "sharpe": (cagr - rf) / vol, "downside_dev": dd_dev,
            "sortino": (cagr - rf) / dd_dev, "max_dd": float(dd.min()), "dd_peak": p.strftime("%Y-%m-%d"), "dd_trough": t.strftime("%Y-%m-%d"),
            "dd_recovered": rec.index[0].strftime("%Y-%m-%d") if len(rec) else None,
            "worst_12m": None if not worst else {"return": float(worst[2]), "from": worst[1].strftime("%Y-%m-%d"), "to": worst[0].strftime("%Y-%m-%d")},
            "best_12m": None if not best else {"return": float(best[2]), "from": best[1].strftime("%Y-%m-%d"), "to": best[0].strftime("%Y-%m-%d")},
            "rolling_12m_windows": len(roll), "calendar_years": cal, "n_returns": int(len(r))}


def main():
    os.makedirs(RAW, exist_ok=True)
    H = {k: dl(v[0]) for k, v in (STOCKS | ETF).items()}
    FX = {c: dl(s) for c, s in FXT.items()}
    KRWUSD = dl("KRW=X")
    cr = rba_cash_rate()

    # trading calendars (days each market has a close)
    cal_us = H["MU"].index.union(H["AVGO"].index).union(H["TSM"].index)
    cal_kr = H["HYNIX"].index; cal_asx = H["SEMI"].index
    metric_cal = cal_us.union(cal_asx)  # ASX/US business days: union of both, forward-filled

    def aud_adj(k):
        sym, cur, _ = (STOCKS | ETF)[k]
        px = H[k]["Adj Close"].dropna()
        if cur == "AUD":
            return px
        fx = FX[cur]["Close"].dropna()
        idx = px.index.union(fx.index)
        return px.reindex(idx).ffill() / fx.reindex(idx).ffill()

    AUD = {k: aud_adj(k) for k in H}
    res = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "periods": {}, "verification": {}, "rf": {}}

    for pk, (s0, e0) in PERIODS.items():
        S, E = pd.Timestamp(s0), pd.Timestamp(e0)
        rf, _ = avg_rate(cr, S, E)
        res["rf"][pk] = rf
        legs, start_info = {}, {}
        for k in H:
            sym, cur, name = (STOCKS | ETF)[k]
            h = H[k]
            ds, ps = first_on_or_after(h["Adj Close"], S); de, pe = last_on_or_before(h["Adj Close"], E)
            _, cs = first_on_or_after(h["Close"], S); _, ce = last_on_or_before(h["Close"], E)
            if cur == "AUD":
                fs = fe = 1.0; fds = fde = ds
            else:
                fds, fs = last_on_or_before(FX[cur]["Close"], ds); fde, fe = last_on_or_before(FX[cur]["Close"], de)
            start_info[k] = {"ticker": sym, "currency": cur, "start_date": ds.strftime("%Y-%m-%d"), "end_date": de.strftime("%Y-%m-%d"),
                             "start_close": cs, "end_close": ce, "start_adj_close": ps, "end_adj_close": pe,
                             "fx_ticker": FXT.get(cur), "fx_start_date": fds.strftime("%Y-%m-%d"), "fx_end_date": fde.strftime("%Y-%m-%d"),
                             "fx_start": fs, "fx_end": fe,
                             "start_aud_adj": ps / fs, "end_aud_adj": pe / fe,
                             "local_return": pe / ps - 1, "fx_effect": (fs / fe) - 1, "aud_return": (pe / fe) / (ps / fs) - 1}
            # A$ value on metrics calendar, starting at the purchase date
            a = AUD[k]
            cal = metric_cal[(metric_cal >= max(ds, S)) & (metric_cal <= E)]
            series = a.reindex(a.index.union(cal)).ffill().reindex(cal)
            amt = INIT_EACH if k in STOCKS else INIT_TOTAL
            legs[k] = series / (ps / fs) * amt
        A = sum(legs[k] for k in STOCKS); B = legs["SEMI"]
        start = max(A.index[0], B.index[0]); A, B = A[A.index >= start], B[B.index >= start]
        out = {"start_rule": "first trading day on/after start date; last trading day on/before end date (each market)",
               "requested": [s0, e0], "rf": rf, "legs": start_info, "metrics": {}}
        for k in list(STOCKS) + ["SEMI"]:
            out["metrics"][k] = metrics(legs[k], rf, legs[k].index[0], legs[k].index[-1])
        out["metrics"]["A"] = metrics(A, rf, A.index[0], A.index[-1])
        out["metrics"]["B"] = out["metrics"]["SEMI"]
        ra, rb = A.pct_change().dropna(), B.pct_change().dropna()
        wa = A.resample("W-FRI").last().pct_change().dropna(); wb = B.resample("W-FRI").last().pct_change().dropna()
        gain = A.iloc[-1] - INIT_TOTAL
        out["relationship"] = {"corr_daily": float(ra.corr(rb)), "beta_daily": float(ra.cov(rb) / rb.var()),
                               "corr_weekly": float(wa.corr(wb)), "beta_weekly": float(wa.cov(wb) / wb.var()),
                               "vol_A": out["metrics"]["A"]["vol"], "vol_B": out["metrics"]["B"]["vol"],
                               "extra_vol_pp": out["metrics"]["A"]["vol"] - out["metrics"]["B"]["vol"],
                               "vol_ratio": out["metrics"]["A"]["vol"] / out["metrics"]["B"]["vol"],
                               "vol_weekly_A": float(wa.std() * math.sqrt(52)), "vol_weekly_B": float(wb.std() * math.sqrt(52))}
        # US-day vs next ASX day (ASX trades after US close): A on day t vs B on next calendar day
        b_next = rb.shift(-1)
        j = pd.concat([ra, b_next], axis=1).dropna()
        out["relationship"]["corr_A_t_vs_B_t+1"] = float(j.iloc[:, 0].corr(j.iloc[:, 1]))
        out["contribution"] = {k: {"start": INIT_EACH, "final": float(legs[k].iloc[-1]), "gain": float(legs[k].iloc[-1] - INIT_EACH),
                                   "share_of_gain": float((legs[k].iloc[-1] - INIT_EACH) / gain), "end_weight": float(legs[k].iloc[-1] / A.iloc[-1])} for k in STOCKS}
        sample = lambda s: [[d.strftime("%Y-%m-%d"), round(float(x), 2)] for d, x in s.items()]
        out["series"] = {"dates": [d.strftime("%Y-%m-%d") for d in A.index], "A": [round(float(x), 2) for x in A], "B": [round(float(x), 2) for x in B.reindex(A.index)],
                         **{k: [round(float(x), 2) for x in legs[k].reindex(A.index)] for k in STOCKS}}
        out["calendar"] = {"metrics": "union of US (NYSE/Nasdaq) and ASX trading days, values forward-filled", "n_days": int(len(A)),
                           "first": A.index[0].strftime("%Y-%m-%d"), "last": A.index[-1].strftime("%Y-%m-%d")}
        res["periods"][pk] = out

    # ---------------- verification of dividends/splits
    ver = {}
    for k in H:
        sym = (STOCKS | ETF)[k][0]; h = H[k]
        acts = h[(h["Dividends"] > 0) | (h.get("Stock Splits", 0) > 0)][["Close", "Dividends", "Stock Splits"]] if "Stock Splits" in h else h[h["Dividends"] > 0][["Close", "Dividends"]]
        acts = acts[acts.index >= "2023-11-01"]
        per = {}
        for pk, (s0, e0) in PERIODS.items():
            s, e = pd.Timestamp(s0), pd.Timestamp(e0)
            trr, pr, dsum = own_tr(h, first_on_or_after(h["Close"], s)[0], last_on_or_before(h["Close"], e)[0])
            ds, ps = first_on_or_after(h["Adj Close"], s); de, pe = last_on_or_before(h["Adj Close"], e)
            per[pk] = {"price_only_return_local": pr, "own_total_return_local": trr, "adj_close_return_local": pe / ps - 1,
                       "adj_minus_own_pp": (pe / ps - 1 - trr) * 100, "dividends_sum_local": dsum,
                       "approx_div_yield_pa": None}
        ev = []
        for d, row in acts.iterrows():
            i = h.index.get_loc(d)
            prev = float(h["Close"].iloc[i - 1]) if i > 0 else None
            item = {"date": d.strftime("%Y-%m-%d"), "dividend": float(row["Dividends"]), "close": float(row["Close"]), "prev_close": prev}
            if "Stock Splits" in row and row["Stock Splits"] > 0:
                item["split"] = float(row["Stock Splits"])
            if prev:
                item["div_pct_of_prev_close"] = float(row["Dividends"]) / prev * 100
                ar = h["Adj Close"].iloc[i] / h["Adj Close"].iloc[i - 1]; cr_ = h["Close"].iloc[i] / h["Close"].iloc[i - 1]
                item["adj_factor_step_pct"] = float((ar / cr_ - 1) * 100)
            ev.append(item)
        ver[k] = {"ticker": sym, "periods": per, "events_since_nov2023": ev}
    # AVGO split continuity
    a = H["AVGO"]; w = a[(a.index >= "2024-07-10") & (a.index <= "2024-07-17")]["Close"]
    ver["AVGO"]["split_check"] = {"closes_around_15jul2024": {d.strftime("%Y-%m-%d"): float(x) for d, x in w.items()},
                                  "note": "Yahoo 'Close' is already split-adjusted (no 10x jump), so split is handled in both Close and Adj Close."}
    # FX cross check for KRW: AUDKRW=X vs KRW=X / ... (KRW=X = KRW per USD; AUDUSD=X = USD per AUD) -> KRW per AUD = KRW=X * AUDUSD
    fxc = {}
    for pk, (s0, e0) in PERIODS.items():
        for lab, d in (("start", pd.Timestamp(s0)), ("end", pd.Timestamp(e0))):
            dd_ = first_on_or_after(FX["KRW"]["Close"], d)[0] if lab == "start" else last_on_or_before(FX["KRW"]["Close"], d)[0]
            direct = float(FX["KRW"]["Close"][dd_]); cross = last_on_or_before(KRWUSD["Close"], dd_)[1] * last_on_or_before(FX["USD"]["Close"], dd_)[1]
            fxc[f"{pk}_{lab}"] = {"date": dd_.strftime("%Y-%m-%d"), "AUDKRW=X": direct, "KRW=X*AUDUSD=X": cross, "diff_pct": (direct / cross - 1) * 100}
    ver["fx_krw_cross_check"] = fxc
    # data completeness: trading days and largest gap per ticker inside the 3y window, NaN check
    dq = {}
    for k in H:
        c = H[k]["Adj Close"]; c = c[(c.index >= "2023-11-01") & (c.index <= "2026-10-30")]
        gaps = c.index.to_series().diff().dt.days.dropna()
        dq[(STOCKS | ETF)[k][0]] = {"trading_days": int(c.notna().sum()), "missing_values": int(c.isna().sum()), "max_gap_days": int(gaps.max()),
                                    "max_gap_end": gaps.idxmax().strftime("%Y-%m-%d"), "first": c.index[0].strftime("%Y-%m-%d"), "last": c.index[-1].strftime("%Y-%m-%d")}
    for c_, t in FXT.items():
        f = FX[c_]["Close"]; f = f[(f.index >= "2023-11-01") & (f.index <= "2026-10-30")]
        dq[t] = {"days": int(f.notna().sum()), "missing_values": int(f.isna().sum()), "max_gap_days": int(f.index.to_series().diff().dt.days.max())}
    ver["data_quality"] = dq
    res["verification"] = ver
    res["rba"] = {"source": "https://www.rba.gov.au/statistics/cash-rate/ (Cash Rate Target, effective dates)",
                  "decisions_used": {d.strftime("%Y-%m-%d"): r for d, r in cr[cr.index >= "2023-05-01"].items()}}
    res["method"] = {
        "prices": "Yahoo Finance via yfinance history(auto_adjust=False): 'Adj Close' (adjusted for splits and cash dividends/distributions, back-adjusted multiplicatively) used as the total-return price.",
        "fx": "USD stocks: A$ = USD adj close / AUDUSD=X close (US$ per A$1). SK hynix: A$ = KRW adj close / AUDKRW=X close (KRW per A$1), cross-checked against KRW=X x AUDUSD=X. FX taken on the same calendar date as the stock close (last FX close on/before if missing).",
        "calendar": "Daily A$ values on the union of US and ASX trading days, each asset's last known close (and FX) forward-filled. SK hynix (KRX) is forward-filled onto that calendar.",
        "timezone": "KRX (15:30 KST) and ASX (16:00 AEST/AEDT) close many hours before the US close (16:00 ET = next morning in Australia). Same-date closes are not simultaneous, so daily A-vs-B correlation and beta are understated; weekly figures and a one-day-lag correlation are shown as a check. Yahoo FX 'close' is a London-evening snapshot, not exactly at any market's close.",
        "cagr": "(V_end / V_start)^(365.25 / calendar days) - 1",
        "vol": "stdev of daily simple returns (sample, ddof=1) x sqrt(252), on the metrics calendar",
        "sharpe": "(CAGR - rf) / vol, rf = time-weighted average RBA cash rate target over the period",
        "sortino": "(CAGR - rf) / downside deviation; downside deviation = sqrt(mean(min(r_d - rf/252, 0)^2)) x sqrt(252) over all days",
        "max_dd": "min over t of V_t / max_{s<=t} V_s - 1 on daily values",
        "rolling_12m": "V_t / V_(last day on/before t-365 days) - 1 for every t at least 365 days after the start",
        "calendar_year": "value at last day on/before 31 Dec of year / value at last day on/before 31 Dec of prior year - 1 (only years fully inside the period)",
        "beta": "cov(r_A, r_B) / var(r_B), daily and weekly (Friday) simple returns",
        "portfolio_A": "A$5,000 in each stock at its first close on/after the start date (with that day's FX), no rebalancing, dividends reinvested via adjusted prices",
        "portfolio_B": "A$20,000 in SEMI.AX at its first close on/after the start date, distributions reinvested via adjusted prices",
        "costs": "No brokerage, FX spreads, taxes or withholding tax on dividends.",
    }
    with open(OUT, "w") as f:
        json.dump(res, f, separators=(",", ":"), default=float)
    print("wrote", OUT, os.path.getsize(OUT))


if __name__ == "__main__":
    main()
