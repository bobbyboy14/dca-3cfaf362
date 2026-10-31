#!/usr/bin/env python3
"""Push the hub's Daily update to bobbyboy14/dca-3cfaf362 as market.json (GitHub Pages).

Usage:  python3 update_market.py path/to/market.json [--message "Daily update 1 Nov"] [--no-push]
Format: {"updated": "2026-11-01T09:30+11:00", "headline": "one short line",
         "assets": {"BTC": {"move": "+1.2%", "note": "one short line"}, "TSLA": {...}, "MSTR": {...}, "SEMI": {...}}}
        "scores": {"BTC": {"status": "On track|Mixed|Off track", "score": 0-10, "line": "one line",
                           "points": {"fundamentals": 0-4, "news": 0-3, "trend": 0-3},
                           "parts": {"fundamentals": "why", "news": "why", "trend": "why"}}, "TSLA": {...}, "MSTR": {...}, "SEMI": {...}}
"needed" (optional): copy of sheet CAGR!H1:Q8 - per asset target, needed, recent (fraction/yr), verdict.
        Data only: "recent" feeds the hub CAGR yearly target boxes. It does NOT feed the score.
"move" must start with + or - (shown green/red). Needs the box's `gh` login.

SCORING RULE (same for all four; total 0-10; no price targets):
  Fundamentals 0-4: Strong 4, Good 3, Mixed 2, Weak or Not verified 1, Bad 0.
     TSLA: latest quarterly report and call.  MSTR: latest quarterly report and call, plus BTC holdings growth,
     financing and mNAV.  SEMI: 'SEMI Scorecard' Whole fund row ("Mostly good" = Good or better).
     BTC: recent US spot-ETF/fund flows, hash rate and network health, adoption and regulation.
  News and risks 0-3: nothing material 3; watch item 2; alert 1; serious damage 0.
  Trend 0-3 (shown on the hub as "Growth"): +1 price above 50-day avg, +1 above 200-day avg,
     +1 weekly RSI (14-wk Wilder) between 35 and 70.  Hub label: 3 On track, 2 Mixed, 0-1 Behind.
  Status: >=7 On track, 4-6 Mixed, <=3 Off track.  score must equal the sum of points.
"""
import argparse, base64, json, subprocess, sys
from datetime import datetime

REPO, PATH, BRANCH = "bobbyboy14/dca-3cfaf362", "market.json", "main"
ASSETS = ["BTC", "TSLA", "MSTR", "SEMI"]
ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--message"); ap.add_argument("--no-push", action="store_true")
a = ap.parse_args()
data = json.load(open(a.file))
for k in ("updated", "headline", "assets"):
    if k not in data: sys.exit(f"needs '{k}'")
try: datetime.fromisoformat(data["updated"])
except ValueError: sys.exit("'updated' must be ISO, e.g. 2026-11-01T09:30+11:00")
for k in ASSETS:
    x = data["assets"].get(k)
    if not x: sys.exit(f"missing asset {k}")
    if not str(x.get("move", "")).startswith(("+", "-")): sys.exit(f"{k}: move must start with + or -, e.g. +1.2%")
    x.setdefault("note", "")
PARTS = {"fundamentals": 4, "news": 3, "trend": 3}  # part -> max points
sc = data.get("scores")
if not isinstance(sc, dict): sys.exit("needs 'scores'")
for k in ASSETS:
    x = sc.get(k)
    if not x: sys.exit(f"scores: missing {k}")
    if x.get("status") not in ("On track", "Mixed", "Off track"): sys.exit(f"scores.{k}: bad status")
    n = x.get("score")
    if not isinstance(n, (int, float)) or not 0 <= n <= 10: sys.exit(f"scores.{k}: score must be 0-10")
    want = "On track" if n >= 7 else "Mixed" if n >= 4 else "Off track"
    if x["status"] != want: sys.exit(f"scores.{k}: score {n} means '{want}'")
    pts = x.get("points", {})
    for p, mx in PARTS.items():
        if not x.get("parts", {}).get(p): sys.exit(f"scores.{k}: missing part '{p}'")
        if not isinstance(pts.get(p), int) or not 0 <= pts[p] <= mx: sys.exit(f"scores.{k}: points.{p} must be 0-{mx}")
    if sum(pts[p] for p in PARTS) != n: sys.exit(f"scores.{k}: score {n} must equal points total {sum(pts[p] for p in PARTS)}")
    x.setdefault("line", "")
nd = data.get("needed")  # optional: {"as_of","source","assets":{K:{"target","needed","recent","verdict"[,"placeholder"]}}}
if nd is not None:
    for k in ASSETS:
        x = nd.get("assets", {}).get(k)
        if not x: sys.exit(f"needed: missing {k}")
        if x.get("verdict") not in ("On track", "Stretch", "Behind"): sys.exit(f"needed.{k}: verdict must be On track, Stretch or Behind")
        if not all(isinstance(x.get(f), (int, float)) for f in ("needed", "recent")): sys.exit(f"needed.{k}: needed/recent must be fractions, e.g. 0.376")
commit = None
if not a.no_push:
    sha = subprocess.run(["gh", "api", f"repos/{REPO}/contents/{PATH}?ref={BRANCH}", "--jq", ".sha"], capture_output=True, text=True).stdout.strip()
    p = {"message": a.message or f"Update market.json ({data['updated']})", "branch": BRANCH,
         "content": base64.b64encode((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()).decode()}
    if sha: p["sha"] = sha
    r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{REPO}/contents/{PATH}", "--input", "-", "--jq", ".commit.sha"], input=json.dumps(p), capture_output=True, text=True)
    if r.returncode: sys.exit("push failed: " + r.stderr)
    commit = r.stdout.strip()
print(json.dumps({"pushed": bool(commit), "commit": commit, "live": "https://bobbyboy14.github.io/dca-3cfaf362/market.json"}))
