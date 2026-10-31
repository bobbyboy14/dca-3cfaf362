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
