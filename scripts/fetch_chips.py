"""Write chips.json (daily AUD prices for the hub's Chips tab) and optionally push it to GitHub Pages.

Run:  cd /workspace/growth-site && /workspace/yfv/bin/python scripts/fetch_chips.py --push
Sources (Yahoo Finance via yfinance, adjusted closes, dividends reinvested):
  MU (US$), AVGO (US$), TSM (TSMC US ADR, US$), 000660.KS (SK hynix, KRW on KRX)
  FX: AUDUSD=X (US$ per A$1), AUDKRW=X (KRW per A$1)
Every calendar day from the common start, gaps (weekends/holidays) carried forward.
"""
import json, math, sys, os, base64, subprocess, datetime as dt, warnings
warnings.filterwarnings("ignore")
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "chips.json")
REPO = "bobbyboy14/dca-3cfaf362"
START = "2021-01-01"
STOCKS = {  # key: (yahoo symbol, currency)
    "MU": ("MU", "USD"),
    "HYNIX": ("000660.KS", "KRW"),
    "AVGO": ("AVGO", "USD"),
    "TSM": ("TSM", "USD"),
}
FX = {"USD": "AUDUSD=X", "KRW": "AUDKRW=X"}


def closes(sym):
    h = yf.Ticker(sym).history(start=START, interval="1d", auto_adjust=True)
    if h.empty:
        raise SystemExit(f"no data for {sym}")
    s = h["Close"].dropna()
    s.index = pd.to_datetime([i.strftime("%Y-%m-%d") for i in s.index])
    s = s[~s.index.duplicated(keep="last")].astype(float)
    s = s[s > 0]
    return s


def main():
    raw = {k: closes(sym) for k, (sym, _) in STOCKS.items()}
    fx = {c: closes(sym) for c, sym in FX.items()}
    start = max(s.index[0] for s in list(raw.values()) + list(fx.values()))
    end = max(s.index[-1] for s in raw.values())
    days = pd.date_range(start, end, freq="D")
    out = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "note": "Adjusted daily closes (Yahoo Finance via yfinance), converted to AUD with that day's AUDUSD / AUDKRW rate; weekends and holidays carried forward.",
           "sources": {k: v[0] for k, v in STOCKS.items()} | {"FX_USD": FX["USD"], "FX_KRW": FX["KRW"]},
           "last_close": {}, "dates": [d.strftime("%Y-%m-%d") for d in days], "aud": {}}
    for k, (sym, cur) in STOCKS.items():
        p = raw[k].reindex(days.union(raw[k].index)).ffill().reindex(days)
        r = fx[cur].reindex(days.union(fx[cur].index)).ffill().reindex(days)
        a = (p / r).round(4)
        if a.isna().any():
            raise SystemExit(f"gaps in {k}")
        out["aud"][k] = [float(x) for x in a]
        out["last_close"][k] = {"date": raw[k].index[-1].strftime("%Y-%m-%d"), "close": round(float(raw[k].iloc[-1]), 4), "currency": cur}
        print(k, sym, len(raw[k]), "last", out["last_close"][k], "A$", out["aud"][k][-1])
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print("wrote", OUT, os.path.getsize(OUT), "bytes,", len(days), "days", out["dates"][0], "to", out["dates"][-1])
    if "--push" in sys.argv:
        push()


def push():
    path = "chips.json"
    sha = subprocess.run(["gh", "api", f"repos/{REPO}/contents/{path}", "--jq", ".sha"], capture_output=True, text=True).stdout.strip()
    body = {"message": "Update chips.json", "content": base64.b64encode(open(OUT, "rb").read()).decode()}
    if sha:
        body["sha"] = sha
    r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{REPO}/contents/{path}", "--input", "-", "--jq", ".commit.sha"],
                       input=json.dumps(body), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("push failed: " + r.stderr)
    print("pushed chips.json commit", r.stdout.strip())


if __name__ == "__main__":
    main()
