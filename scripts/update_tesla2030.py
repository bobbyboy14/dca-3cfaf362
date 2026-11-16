"""Weekly refresh of tesla-2030.html: latest closes for TSLA, SPCX, SEMI.AX and AUD/USD.
Updates the starting prices, the start date, the price stamp and the rolling CAGR projection (ROLL block). The page recalculates everything else in the browser."""
import re, datetime, yfinance as yf
from zoneinfo import ZoneInfo

P = "tesla-2030.html"
s = open(P, encoding="utf-8").read()

def last_close(t):
    h = yf.Ticker(t).history(period="10d", interval="1d")["Close"].dropna()
    if h.empty:
        return None, None
    return float(h.iloc[-1]), h.index[-1].date()

def setval(html, el, v):
    new, n = re.subn(r'(id="%s"[^>]*?value=")[^"]*(")' % el, r"\g<1>%s\g<2>" % v, html, count=1)
    if n != 1:
        raise SystemExit("could not find input " + el)
    return new

notes, dates = [], []
for el, tk, dp in [("t_p0", "TSLA", 2), ("s_p0", "SPCX", 2), ("m_p0", "SEMI.AX", 2), ("fx", "AUDUSD=X", 4)]:
    try:
        px, d = last_close(tk)
    except Exception as e:
        px, d = None, None
        print(tk, "error", e)
    if px is None:
        notes.append(tk + " price unavailable this week, kept last value")
        continue
    s = setval(s, el, f"{px:.{dp}f}")
    if el != "fx":
        dates.append(d)
    print(tk, round(px, dp), d)

# ---- Rolling CAGR projection (6m/12m/3y adjusted-price CAGRs, blended 25/50/25) ----
import json, pandas as pd
END = datetime.date(2030, 12, 31)
PERIODS = [("6m", 6, 0.25), ("12m", 12, 0.50), ("3y", 36, 0.25)]
LO, HI = -0.40, 0.80   # sensible caps on any annualised rate used for projecting

def rolling(tk):
    h = yf.Ticker(tk).history(period="5y", interval="1d", auto_adjust=True)["Close"].dropna()
    if len(h) < 40:
        return None
    h.index = h.index.tz_localize(None).normalize()
    last_d, cur = h.index[-1], float(h.iloc[-1])
    rates, used, wsum = {}, [], 0.0
    for k, months, w in PERIODS:
        then = last_d - pd.DateOffset(months=months)
        if h.index[0] > then + pd.Timedelta(days=5):
            rates[k] = None
            continue
        p0 = float(h[h.index <= then].iloc[-1]) if (h.index <= then).any() else float(h.iloc[0])
        yrs = months / 12
        rates[k] = (cur / p0) ** (1 / yrs) - 1
        used.append((k, w))
        wsum += w
    since = None
    if not used:  # too new for any period: fall back to since-listing, annualised
        yrs = (last_d - h.index[0]).days / 365.25
        since = {"from": h.index[0].date().isoformat(), "months": round(yrs * 12, 1),
                 "cagr": (cur / float(h.iloc[0])) ** (1 / yrs) - 1}
        pool = [since["cagr"]]
        blend_raw = since["cagr"]
    else:
        pool = [rates[k] for k, _ in used]
        blend_raw = sum(rates[k] * w for k, w in used) / wsum
    cl = lambda r: max(LO, min(HI, r))
    years = (END - last_d.date()).days / 365.25
    out = {"asof": last_d.date().isoformat(), "cur": round(cur, 4), "years": round(years, 4),
           "r6m": rates.get("6m"), "r12m": rates.get("12m"), "r3y": rates.get("3y"),
           "used": [k for k, _ in used], "weights": {k: round(w / wsum, 4) for k, w in used} if used else {},
           "since": since, "blend_raw": blend_raw, "blend": cl(blend_raw),
           "low": cl(min(pool)), "high": cl(max(pool)), "capped": any(r != cl(r) for r in pool + [blend_raw])}
    for k in ("r6m", "r12m", "r3y", "blend_raw", "blend", "low", "high"):
        if out[k] is not None:
            out[k] = round(out[k], 5)
    if since:
        since["cagr"] = round(since["cagr"], 5)
    for k, r in (("p_blend", out["blend"]), ("p_low", out["low"]), ("p_high", out["high"])):
        out[k] = round(cur * (1 + r) ** years, 2)
    return out

roll = {}
for key, tk in (("t", "TSLA"), ("s", "SPCX"), ("m", "SEMI.AX")):
    try:
        r = rolling(tk)
    except Exception as e:
        r = None
        print(tk, "rolling error", e)
    if r:
        roll[key] = r
        print(tk, "rolling", json.dumps(r))
old_roll = re.search(r"/\*ROLL\*/(.*?)/\*/ROLL\*/", s, flags=re.S)
if old_roll is None:
    raise SystemExit("ROLL marker not found")
prev = json.loads(old_roll.group(1)) if old_roll.group(1).strip() else {}
for k in ("t", "s", "m"):
    if k not in roll and k in prev:
        roll[k] = prev[k]
        notes.append({"t": "TSLA", "s": "SPCX", "m": "SEMI.AX"}[k] + " rolling growth unavailable this week, kept last values")
s = s[:old_roll.start(1)] + json.dumps(roll, separators=(",", ":")) + s[old_roll.end(1):]

today = datetime.datetime.now(ZoneInfo("Australia/Melbourne")).date()
s = setval(s, "start", today.isoformat())
asof = max(dates).strftime("%-d %b %Y") if dates else "the last update"
msg = f"Starting prices are closing prices from {asof} (refreshed {today.strftime('%-d %b %Y')}) and refresh automatically every Sunday morning."
if notes:
    msg += " " + "; ".join(notes) + "."
s = re.sub(r"<!--PX-->.*?<!--/PX-->", "<!--PX-->" + msg + "<!--/PX-->", s, flags=re.S)
open(P, "w", encoding="utf-8").write(s)
