"""Weekly refresh of tesla-2030.html: latest closes for TSLA, SPCX, SEMI.AX and AUD/USD.
Updates the starting prices, the start date and the price stamp. The page recalculates everything else in the browser."""
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

today = datetime.datetime.now(ZoneInfo("Australia/Melbourne")).date()
s = setval(s, "start", today.isoformat())
asof = max(dates).strftime("%-d %b %Y") if dates else "the last update"
msg = f"Starting prices are closing prices from {asof} (refreshed {today.strftime('%-d %b %Y')}) and refresh automatically every Sunday morning."
if notes:
    msg += " " + "; ".join(notes) + "."
s = re.sub(r"<!--PX-->.*?<!--/PX-->", "<!--PX-->" + msg + "<!--/PX-->", s, flags=re.S)
open(P, "w", encoding="utf-8").write(s)
