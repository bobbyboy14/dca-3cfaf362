#!/usr/bin/env python3
"""Last price and 1-day move for SEMI's 30 holdings -> holdings.json (run by the GitHub Actions workflow)."""
import json, datetime, yfinance as yf
T = {"NVIDIA": "NVDA", "Micron": "MU", "TSMC": "2330.TW", "AMD": "AMD", "Broadcom": "AVGO", "SK hynix": "000660.KS",
     "ASML": "ASML.AS", "Intel": "INTC", "Applied Materials": "AMAT", "Lam Research": "LRCX", "Texas Instruments": "TXN",
     "KLA": "KLAC", "Analog Devices": "ADI", "Qualcomm": "QCOM", "Marvell": "MRVL", "MediaTek": "2454.TW", "Advantest": "6857.T",
     "Tokyo Electron": "8035.T", "Kioxia": "285A.T", "Infineon": "IFX.DE", "ASE Technology": "3711.TW", "NXP": "NXPI",
     "TE Connectivity": "TEL", "Monolithic Power": "MPWR", "Samsung Electro-Mechanics": "009150.KS", "Coherent": "COHR",
     "Teradyne": "TER", "UMC": "2303.TW", "Astera Labs": "ALAB", "Renesas": "6723.T"}
out = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "holdings": {}}
for name, t in T.items():
    try:
        tk = yf.Ticker(t); h = tk.history(period="10d", auto_adjust=False)["Close"].dropna()
        cur = (tk.fast_info.get("currency") or "")
        out["holdings"][name] = {"ticker": t, "currency": cur, "date": str(h.index[-1].date()), "close": round(float(h.iloc[-1]), 2),
                                 "change": round(float(h.iloc[-1] / h.iloc[-2] - 1), 5)}
    except Exception as e:
        out["holdings"][name] = {"ticker": t, "error": str(e)[:80]}
json.dump(out, open("holdings.json", "w"), indent=1)
print(sum("close" in v for v in out["holdings"].values()), "of", len(T), "prices")
