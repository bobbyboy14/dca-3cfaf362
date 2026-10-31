"""Write data.json with daily closes + latest prices for the Basket growth page."""
import json, math, datetime as dt
import yfinance as yf

SYMS = {"BTC": "BTC-USD", "TSLA": "TSLA", "MSTR": "MSTR", "SEMI": "SEMI.AX", "AUDUSD": "AUDUSD=X"}
START = "2021-01-01"

out = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
       "note": "Daily closes from Yahoo Finance via yfinance, adjusted for splits and distributions (SEMI payouts reinvested). BTC, TSLA, MSTR in USD; SEMI in AUD; AUDUSD = US$ per A$1.",
       "series": {}, "latest": {}}
for key, sym in SYMS.items():
    t = yf.Ticker(sym)
    h = t.history(start=START, interval="1d", auto_adjust=True)
    if h.empty:
        raise SystemExit(f"no data for {sym}")
    rows = []
    for idx, c in h["Close"].items():
        if c is None or (isinstance(c, float) and math.isnan(c)):
            continue
        rows.append([idx.strftime("%Y-%m-%d"), round(float(c), 6)])
    out["series"][key] = rows
    # latest price: try intraday, fall back to last daily close
    # latest = last daily row (yfinance includes today's live row while a market is open);
    # take the timestamp from the newest 5-minute bar so the page can show how fresh it is.
    price, when = rows[-1][1], h.index[-1].isoformat()
    try:
        i = t.history(period="5d", interval="5m")["Close"].dropna()
        if not i.empty and i.index[-1].strftime("%Y-%m-%d") >= rows[-1][0]:
            when = i.index[-1].isoformat()
    except Exception as e:
        print("intraday failed", sym, e)
    out["latest"][key] = {"price": price, "time": when}
    print(key, len(rows), rows[-1], out["latest"][key])

with open("data.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))


# ---------------------------------------------------------------- today + SEMI signals
import pandas as pd

def ser(key):
    s = pd.Series({pd.Timestamp(d): v for d, v in out["series"][key]}).sort_index()
    return s

S = {k: ser(k) for k in SYMS}
fx = S["AUDUSD"]

def in_aud(key):
    s = S[key]
    if key in ("BTC", "TSLA", "MSTR"):
        return s / fx.reindex(s.index, method="ffill")
    return s

def pct(a, b):
    return None if (a is None or b is None or b == 0) else round(a / b - 1, 6)

today = {}
for key in SYMS:
    s = S[key]
    today[key] = {"date": s.index[-1].strftime("%Y-%m-%d"), "close": round(float(s.iloc[-1]), 6),
                  "prev_date": s.index[-2].strftime("%Y-%m-%d"), "prev_close": round(float(s.iloc[-2]), 6),
                  "change": pct(float(s.iloc[-1]), float(s.iloc[-2]))}
out["today"] = today

semi = S["SEMI"]
sma50 = semi.rolling(50).mean()
sma200 = semi.rolling(200).mean()
price = float(semi.iloc[-1])
mayer = price / float(sma200.iloc[-1])

def rsi_wilder(series, n=14):
    d = series.diff().dropna()
    up = d.clip(lower=0); dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False).mean(); ad = dn.ewm(alpha=1 / n, adjust=False).mean()
    rs = au / ad
    return 100 - 100 / (1 + rs)

weekly = semi.resample("W-FRI").last().dropna()
wrsi = float(rsi_wilder(weekly).iloc[-1])
hi52 = float(semi[semi.index > semi.index[-1] - pd.Timedelta(days=365)].max())

# 200-day cross in the last 5 trading days
above = (semi > sma200).dropna()
recent = above.iloc[-6:]
cross = None
if recent.nunique() > 1:
    cross = "up" if bool(recent.iloc[-1]) else "down"

reasons = []
if wrsi > 70: reasons.append(f"Weekly RSI is {wrsi:.0f}, above 70 (stretched to the upside)")
if wrsi < 30: reasons.append(f"Weekly RSI is {wrsi:.0f}, below 30 (heavily sold off)")
if cross == "up": reasons.append("Price crossed above its 200-day average in the last week")
if cross == "down": reasons.append("Price crossed below its 200-day average in the last week")
if mayer > 1.30: reasons.append(f"Price is {(mayer - 1) * 100:.0f}% above its 200-day average (more than 30%)")

# comparisons in AUD
aud = {k: in_aud(k) for k in ("SEMI", "TSLA", "BTC", "MSTR")}
def move(s, days):
    end = s.index[-1]
    past = s[s.index <= end - pd.Timedelta(days=days)]
    return pct(float(s.iloc[-1]), float(past.iloc[-1])) if len(past) else None
semi_ret = aud["SEMI"].pct_change()
compare = {}
for k, s in aud.items():
    r = s.pct_change()
    joined = pd.concat([semi_ret, r], axis=1, join="inner").dropna().iloc[-90:]
    corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1])) if k != "SEMI" else 1.0
    # US/crypto trade overnight after the ASX closes, so also compare SEMI's day with the previous overseas session
    lag = None
    if k != "SEMI":
        a = semi_ret.dropna().rename("semi").to_frame().reset_index(names="d")
        b = r.dropna().rename("x").to_frame().reset_index(names="d")
        lag = pd.merge_asof(a, b, on="d", allow_exact_matches=False).dropna()[["semi", "x"]].iloc[-90:]
    corr_lag = float(lag.iloc[:, 0].corr(lag.iloc[:, 1])) if lag is not None else 1.0
    compare[k] = {"d1": pct(float(s.iloc[-1]), float(s.iloc[-2])), "m1": move(s, 30),
                  "corr90": round(corr, 3), "corr90_next_day": round(corr_lag, 3), "last_date": s.index[-1].strftime("%Y-%m-%d")}

fx_d1 = pct(float(fx.iloc[-1]), float(fx.iloc[-2]))
fx_m1 = move(fx, 30)
if fx_m1 is None or abs(fx_m1) < 0.002:
    fx_effect = "neutral"
else:
    fx_effect = "helping" if fx_m1 < 0 else "hurting"

out["semi_signals"] = {
    "date": semi.index[-1].strftime("%Y-%m-%d"), "price": round(price, 4),
    "sma50": round(float(sma50.iloc[-1]), 4), "sma200": round(float(sma200.iloc[-1]), 4),
    "vs_sma50": pct(price, float(sma50.iloc[-1])), "vs_sma200": pct(price, float(sma200.iloc[-1])),
    "mayer": round(mayer, 4), "weekly_rsi": round(wrsi, 2), "high_52w": round(hi52, 4),
    "from_high_52w": pct(price, hi52), "cross_200": cross,
    "status": "Notable" if reasons else "Nothing notable", "reasons": reasons,
    "compare": compare,
    "audusd": {"rate": round(float(fx.iloc[-1]), 6), "d1": fx_d1, "m1": fx_m1, "effect_on_semi": fx_effect},
    "method": "Adjusted daily closes. RSI = 14-week Wilder on Friday closes. Moves and correlations in AUD; correlation = last 90 shared trading days of daily returns.",
}
print("signals", json.dumps({k: v for k, v in out["semi_signals"].items() if k != "compare"}, default=str))
print("compare", out["semi_signals"]["compare"])

# ---------------------------------------------------------------- year-by-year history in AUD (asset's own record)
yearly = {}
for k in ("TSLA", "MSTR", "SEMI"):
    s_aud = in_aud(k).dropna()
    end = s_aud.index[-1]
    def at(ts):
        sub = s_aud[s_aud.index <= ts]
        return (sub.index[-1], float(sub.iloc[-1])) if len(sub) else (None, None)
    pts = [at(end - pd.DateOffset(years=n)) for n in range(5, -1, -1)]
    rows, val = [], 10000.0
    for i in range(5):
        (d0, p0), (d1, p1) = pts[i], pts[i + 1]
        if p0 is None:
            rows.append({"year": i + 1, "start_date": None}); continue
        val = val * p1 / p0 if rows and rows[-1].get("start_date") else 10000.0 * p1 / p0
        rows.append({"year": i + 1, "start_date": d0.strftime("%Y-%m-%d"), "end_date": d1.strftime("%Y-%m-%d"),
                     "start_aud": round(p0, 4), "end_aud": round(p1, 4), "change": pct(p1, p0), "value_10k": round(val, 2)})
    yearly[k] = rows
out["yearly_aud"] = yearly
print("yearly", {k: [(r.get("change"), r.get("value_10k")) for r in v] for k, v in yearly.items()})

# ---------------------------------------------------------------- value-indicator inputs (AUD, each asset's own trading days)
vi = {}
for k in ("BTC", "TSLA", "MSTR", "SEMI"):
    a = in_aud(k).dropna()
    last = a.index[-1]
    yr = a[a.index > last - pd.Timedelta(days=365)]
    vi[k] = {"date": last.strftime("%Y-%m-%d"), "price_aud": round(float(a.iloc[-1]), 4),
             "high_52w_aud": round(float(yr.max()), 4), "high_52w_date": yr.idxmax().strftime("%Y-%m-%d"),
             "sma200_aud": round(float(a.iloc[-200:].mean()), 4)}
out["value_inputs"] = vi
print("value_inputs", vi)

with open("data.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
