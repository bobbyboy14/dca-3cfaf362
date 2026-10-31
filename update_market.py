#!/usr/bin/env python3
"""Push the hub's Daily update to bobbyboy14/dca-3cfaf362 as market.json (GitHub Pages).

Usage:  python3 update_market.py path/to/market.json [--message "Daily update 1 Nov"] [--no-push]
Format: {"updated": "2026-11-01T09:30+11:00", "headline": "one short line",
         "assets": {"BTC": {"move": "+1.2%", "note": "one short line"}, "TSLA": {...}, "MSTR": {...}, "SEMI": {...}}}
"move" must start with + or - (shown green/red). Needs the box's `gh` login.
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
