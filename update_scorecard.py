#!/usr/bin/env python3
"""Rebuild scorecard.json (hub.html#scorecard) from the sheet's 'SEMI Scorecard' tab and push it.

Usage:  python3 update_scorecard.py <tab.csv | read_range.json> [--no-push] [--message "..."]
Input:  the tab 'SEMI Scorecard'!A1:F44 of spreadsheet 1W7DVERD6sZYiozCwFvM9jsiaSefbZuiadeKEyMek_KU, either
        saved as CSV, or the raw JSON returned by the Google Sheets connector read_range (write_to_file).
Rows used: row 3 "As of ...", the header "Company,Weight,...", one row per holding, the "Whole fund" row,
        and the text under "What to watch". Needs the box's `gh` login.
"""
import argparse, base64, csv, io, json, re, subprocess, sys

REPO, PATH, BRANCH = "bobbyboy14/dca-3cfaf362", "scorecard.json", "main"
ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--no-push", action="store_true"); ap.add_argument("--message")
a = ap.parse_args()
raw = open(a.file, encoding="utf-8").read()
m = re.search(r'\{"spreadsheetId".*\}', raw, re.S)
if m: raw = json.loads(m.group(0))["ranges"][0]["content"]
rows = list(csv.reader(io.StringIO(raw)))
out = {"as_of": "", "holdings": [], "overall": None, "watch": ""}
i = 0; mode = None
for r in rows:
    c = [x.strip() for x in r] + [""] * 6
    if c[0].startswith("As of"): out["as_of"] = c[0]
    elif c[0] == "Company": mode = "h"
    elif mode == "h" and c[0] == "Whole fund":
        out["overall"] = {"weight": c[1], "dates": c[2], "verdict": c[3], "flag": c[4]}; mode = None
    elif mode == "h" and c[0]:
        out["holdings"].append({"company": c[0], "weight": c[1], "date": c[2], "verdict": c[3], "flag": c[4], "source": c[5]})
    elif c[0] == "What to watch": mode = "w"
    elif mode == "w" and c[0]: out["watch"] = c[0]; mode = None
if len(out["holdings"]) < 10 or not out["overall"]: sys.exit("couldn't find holdings / Whole fund row")
for h in out["holdings"]:
    if h["verdict"] not in ("Good", "Mixed", "Bad", "Not verified"): sys.exit(f"{h['company']}: odd verdict {h['verdict']!r}")
body = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
open("/workspace/growth-site/scorecard.json", "w").write(body)
commit = None
if not a.no_push:
    sha = subprocess.run(["gh", "api", f"repos/{REPO}/contents/{PATH}?ref={BRANCH}", "--jq", ".sha"], capture_output=True, text=True).stdout.strip()
    p = {"message": a.message or "Update scorecard.json", "branch": BRANCH, "content": base64.b64encode(body.encode()).decode()}
    if sha: p["sha"] = sha
    r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{REPO}/contents/{PATH}", "--input", "-", "--jq", ".commit.sha"], input=json.dumps(p), capture_output=True, text=True)
    if r.returncode: sys.exit("push failed: " + r.stderr)
    commit = r.stdout.strip()
print(json.dumps({"holdings": len(out["holdings"]), "overall": out["overall"]["verdict"], "pushed": bool(commit), "commit": commit}))
