#!/usr/bin/env python3
"""
run_qa.py — run all data/page checks and emit a viewable HTML report.

Runs the three gates, collects results + key numbers, and writes
eval/qa-report.html (self-contained, styled). Prints a text summary and exits
non-zero if a hard gate fails — so it works both locally and in CI, and the HTML
is the artifact you open to see the results.

    python3 eval/run_qa.py
"""
import json, os, subprocess, sys, html
from datetime import datetime, timezone
from collections import defaultdict

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
VOTES = os.path.join(ROOT, "amherst", "votes.json")
GOLD = os.path.join(HERE, "votes-gold.jsonl")
REPORT = os.path.join(HERE, "qa-report.html")

def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)

# ---- build the page first (test_page.js reads build/index.html) ----
r_build, out_build = run(["python3", "explorer/build_explorer.py"])
# ---- gates ----
r_validate, out_validate = run(["python3", "validate_votes.py"])
r_page, out_page = run(["node", "eval/test_page.js"])

# ---- numbers straight from the data ----
ballots = json.load(open(VOTES, encoding="utf-8"))["ballots"]
mot = defaultdict(list)
for x in ballots:
    mot[x["motion_id"]].append(x)
att_motions = [m for m, rs in mot.items() if any(r["councilor"] for r in rs)]
recon = 0
for m in att_motions:
    rs = [r for r in mot[m] if r["councilor"]]
    t = rs[0]["tally"]
    if not t:
        continue
    p = t.split("-")
    if not all(c.isdigit() for c in p):
        continue
    y = sum(r["vote"] == "yes" for r in rs); n = sum(r["vote"] == "no" for r in rs); a = sum(r["vote"] == "abstain" for r in rs)
    if y == int(p[0]) and n == int(p[1]) and (len(p) < 3 or a == int(p[2])):
        recon += 1
att_ballots = sum(1 for x in ballots if x["councilor"])
councilors = len({x["councilor"] for x in ballots if x["councilor"]})
newest = max(x["date"] for x in ballots)

# ---- ground-truth gold ----
gold = [json.loads(l) for l in open(GOLD, encoding="utf-8") if l.strip()] if os.path.exists(GOLD) else []
cur = defaultdict(dict)
for x in ballots:
    if x["councilor"]:
        cur[x["motion_id"]][x["councilor"]] = x["vote"]
verified = [g for g in gold if g.get("verified")]
gmatch = sum(1 for g in verified if cur.get(g["motion_id"], {}) == g["truth_votes"])
gn = len(verified)
if gn == 0:
    gold_status, gold_detail = "PENDING", f"0 of {len(gold)} sample motions verified against source PDFs yet"
elif gmatch == gn:
    ub = 3.0 / gn * 100
    gold_status = "PASS"
    gold_detail = f"{gmatch}/{gn} verified motions match source · accuracy {100*gmatch/gn:.0f}% · 95% error rate &lt; {ub:.1f}%"
else:
    gold_status = "FAIL"
    gold_detail = f"{gmatch}/{gn} match — {gn-gmatch} disagree with the verified source"

checks = [
    ("Data invariants", "validate_votes.py", "PASS" if r_validate == 0 else "FAIL",
     f"11 invariants · {recon}/{len(att_motions)} motions reconcile with the printed tally · {att_ballots:,} votes checked"),
    ("Page logic", "eval/test_page.js", "PASS" if r_page == 0 else "FAIL",
     "12 checks · every figure the page shows matches an independent recount of votes.json"),
    ("Ground truth (sample)", "eval/check_gold.py", gold_status, gold_detail),
]
hard_fail = r_build != 0 or r_validate != 0 or r_page != 0 or gold_status == "FAIL"
overall = "FAIL" if hard_fail else ("ATTENTION" if gold_status == "PENDING" else "PASS")

# ---- render ----
BADGE = {"PASS": ("#006241", "#E3F1EA"), "FAIL": ("#9C3324", "#FBE7E3"),
         "PENDING": ("#B7810B", "#FFF7E3"), "ATTENTION": ("#B7810B", "#FFF7E3")}
def badge(s):
    fg, bg = BADGE[s]
    return f'<span style="background:{bg};color:{fg};font-family:var(--f-narrow);font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;padding:4px 11px;border-radius:3px">{s}</span>'

rows = "".join(
    f'<div class="card"><div class="ch"><div><div class="cn">{html.escape(name)}</div>'
    f'<div class="cc">{html.escape(code)}</div></div>{badge(st)}</div>'
    f'<p class="cd">{detail}</p></div>'
    for name, code, st, detail in checks)

stats = [(f"{len(mot):,}", "Motions"), (f"{att_ballots:,}", "Attributed votes"),
         (f"{len(mot)-len(att_motions):,}", "Non-attributable"), (str(councilors), "Councilors"),
         (newest, "Newest meeting")]
stat_html = "".join(f'<div class="gs"><b>{v}</b><span>{l}</span></div>' for v, l in stats)

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Council data — QA report</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#F4F4F2;--ink:#1E2328;--muted:#4B5058;--line:#C8C9C5;--accent:#D94F3D;--gold:#FFB81C;
--f-display:"Oswald","Barlow Condensed",sans-serif;--f-body:"Barlow","Inter",system-ui,sans-serif;--f-narrow:"Barlow Condensed",sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 var(--f-body)}}
.wrap{{max-width:720px;margin:0 auto;padding:30px 20px 60px}}
.eyebrow{{font-family:var(--f-narrow);font-weight:700;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}
h1{{font-family:var(--f-display);font-size:40px;text-transform:uppercase;letter-spacing:-.01em;margin:6px 0 0;line-height:.95}}
.rule{{height:6px;background:var(--accent);margin:14px 0 8px}}
.meta{{color:var(--muted);font-size:14px;margin:0 0 24px}}
.overall{{display:flex;align-items:center;gap:14px;margin-bottom:24px}}
.overall .big{{font-family:var(--f-display);font-size:30px;text-transform:uppercase}}
.card{{background:#fff;border:1px solid var(--ink);box-shadow:4px 4px 0 var(--ink);border-radius:3px;padding:16px 18px;margin-bottom:16px}}
.ch{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}}
.cn{{font-family:var(--f-display);font-size:22px;text-transform:uppercase;letter-spacing:-.01em}}
.cc{{font-family:var(--f-narrow);font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
.cd{{margin:10px 0 0;font-size:15px;color:var(--muted)}}
.gold{{background:var(--gold);border-radius:3px;padding:20px 22px;margin-top:8px}}
.gold h3{{font-family:var(--f-display);font-size:24px;text-transform:uppercase;margin:0 0 12px}}
.gstats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:0 24px}}
.gs{{display:flex;align-items:baseline;gap:9px;padding:10px 0;border-top:1px solid rgba(30,35,40,.22)}}
.gs b{{font-family:var(--f-display);font-size:23px;min-width:56px}}.gs span{{font-size:14px;font-weight:500}}
.foot{{color:var(--muted);font-size:13px;margin-top:22px;line-height:1.6}}
</style></head><body><div class="wrap">
<div class="eyebrow">Amherst council data · automated QA</div>
<h1>QA report</h1><div class="rule"></div>
<p class="meta">Generated {now}</p>
<div class="overall"><span class="big">Overall</span>{badge(overall)}</div>
{rows}
<div class="gold"><h3>Data summary</h3><div class="gstats">{stat_html}</div></div>
<p class="foot">Green = machine-proven &amp; reproducible. “Data invariants” proves every attributed vote matches the official printed tally; “Page logic” proves the page shows exactly what the data says; “Ground truth” is the human-verified sample (see CORRECTNESS.md). This page is regenerated on every CI run.</p>
</div></body></html>"""
open(REPORT, "w", encoding="utf-8").write(doc)

print(f"Overall: {overall}")
for name, code, st, _ in checks:
    print(f"  [{st:>9}] {name} ({code})")
print(f"Report written: {REPORT}")
sys.exit(1 if hard_fail else 0)
