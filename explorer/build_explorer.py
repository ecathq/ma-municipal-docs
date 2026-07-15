#!/usr/bin/env python3
"""
build_explorer.py — regenerate the static Council Data Explorer.

Reads explorer/explorer.template.html + amherst/votes.json and writes the
built, self-contained page to explorer-site/index.html (data embedded). Run
whenever votes.json changes; CI does this automatically (build-explorer.yml).

    python3 explorer/build_explorer.py
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "explorer", "explorer.template.html")
VOTES = os.path.join(ROOT, "amherst", "votes.json")
OUT = os.path.join(ROOT, "build", "index.html")   # transient; pushed to the app repo by CI

def main():
    d = json.load(open(VOTES, encoding="utf-8"))
    b = d["ballots"]
    order, idx = [], {}
    for x in b:
        mid = x["motion_id"]
        if mid not in idx:
            idx[mid] = len(order)
            t = x["tally"]; con = 0
            if t:
                p = t.split("-")
                no = int(p[1]) if len(p) > 1 else 0
                ab = int(p[2]) if len(p) > 2 else 0
                con = 1 if (no > 0 or ab > 0) else 0
            rec = {"d": x["date"], "t": x["topic_tags"], "tl": x["tally"], "con": con,
                   "m": x["motion_text"][:160], "s": x["source_pdf"]}
            if x.get("mover"): rec["by"] = x["mover"]
            if x.get("seconder"): rec["se"] = x["seconder"]
            order.append(rec)
    M = order
    B = [{"c": x["councilor"], "v": x["vote"], "i": idx[x["motion_id"]]}
         for x in b if x["councilor"]]
    meta = {"attributable_ballots": d["meta"]["attributable_ballots"],
            "source_files": d["meta"]["source_files"]}
    tpl = open(TPL, encoding="utf-8").read()
    html = (tpl.replace("__M__", json.dumps(M, ensure_ascii=False, separators=(",", ":")))
               .replace("__B__", json.dumps(B, separators=(",", ":")))
               .replace("__META__", json.dumps(meta)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"built {OUT} ({round(len(html)/1024)} KB) — {len(M)} motions, {len(B)} ballots")

if __name__ == "__main__":
    main()
