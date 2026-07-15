#!/usr/bin/env python3
"""
validate_votes.py — automated correctness checks for amherst/votes.json.

This is the deterministic half of evaluation: the vote dataset is produced by
regex/rules, so it is checked with invariants, not an LLM. The headline
invariant is reconciliation — every attributed vote must match the printed
tally exactly. Run after every build; exits non-zero if any check fails.

    python3 validate_votes.py            # full report
    python3 validate_votes.py --quiet    # only failures + summary

Pairs with eval/votes-audit.html (human spot-check vs the source PDFs) and
eval/promptfoo-topics.yaml (LLM-as-judge grading of the fuzzy topic tags).
"""
import json, re, sys, os
from collections import defaultdict, Counter

PATH = os.path.join(os.path.dirname(__file__), "amherst", "votes.json")
VOTE_VALUES = {"yes", "no", "abstain", "absent"}
METHODS = {"roll_call", "unanimous", "voice_unanimous", "voice_named",
           "voice_expanded", "non_attributable", "unknown"}
ALLOWED_TOPICS = {"jones-library", "schools", "budget-appropriation", "zoning",
                  "cpa", "appointments", "climate-energy", "rules-procedure",
                  "resolution"}
ADID_RE = re.compile(r"Archive\.aspx\?ADID=\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

quiet = "--quiet" in sys.argv
results = []  # (name, ok, detail)

def check(name, failures, sample=None):
    ok = len(failures) == 0
    results.append((name, len(failures), sample if sample else failures[:3]))
    return ok

def main():
    data = json.load(open(PATH, encoding="utf-8"))
    b = data["ballots"]

    # canonical councilor set = names that appear as an attributed voter
    canon = {x["councilor"] for x in b if x["councilor"]}

    # ---- 1. schema / value domains ----
    bad_fields, bad_vote, bad_method, bad_date, bad_src, bad_topic = ([] for _ in range(6))
    bad_mover = []
    REQ = {"councilor", "vote", "date", "motion_id", "topic_tags",
           "tally", "vote_method", "source_pdf"}
    for x in b:
        if not REQ <= x.keys():
            bad_fields.append(x.get("motion_id"))
        if x["vote"] not in VOTE_VALUES and x["vote"] is not None:
            bad_vote.append((x["motion_id"], x["vote"]))
        if x["vote_method"] not in METHODS:
            bad_method.append((x["motion_id"], x["vote_method"]))
        if not DATE_RE.match(x["date"]):
            bad_date.append((x["motion_id"], x["date"]))
        if x["source_pdf"] and not ADID_RE.search(x["source_pdf"]):
            bad_src.append((x["motion_id"], x["source_pdf"]))
        for t in x["topic_tags"]:
            if t not in ALLOWED_TOPICS:
                bad_topic.append((x["motion_id"], t))
        for who in (x.get("mover"), x.get("seconder")):
            if who is not None and who not in canon:
                bad_mover.append((x["motion_id"], who))

    check("required fields present", bad_fields)
    check("vote value in {yes,no,abstain,absent,null}", bad_vote)
    check("vote_method in allowed set", bad_method)
    check("date is YYYY-MM-DD", bad_date)
    check("source_pdf is an Archive.aspx ADID url", bad_src)
    check("topic_tags from allowed vocabulary", bad_topic)
    check("mover/seconder is a known councilor or null", bad_mover)

    # ---- 2. per-motion consistency ----
    by_motion = defaultdict(list)
    for x in b:
        by_motion[x["motion_id"]].append(x)
    inconsistent_meta, mixed_stub, dup_vote = [], [], []
    for mid, rows in by_motion.items():
        for f in ("date", "tally", "vote_method", "source_pdf"):
            if len({r[f] for r in rows}) > 1:
                inconsistent_meta.append((mid, f))
        attributed = [r for r in rows if r["councilor"]]
        stubs = [r for r in rows if not r["councilor"]]
        if attributed and stubs:
            mixed_stub.append(mid)
        seen = Counter(r["councilor"] for r in attributed)
        for c, n in seen.items():
            if n > 1:
                dup_vote.append((mid, c, n))
    check("motion metadata consistent across its ballots", inconsistent_meta)
    check("no motion mixes attributed votes with a null stub", mixed_stub)
    check("each councilor votes at most once per motion", dup_vote)

    # ---- 3. THE headline invariant: reconciliation ----
    mismatch = []
    for mid, rows in by_motion.items():
        att = [r for r in rows if r["councilor"]]
        if not att:
            continue
        tally = att[0]["tally"]
        if not tally:
            mismatch.append((mid, "attributed but no tally"))
            continue
        parts = tally.split("-")
        if not all(p.isdigit() for p in parts):
            continue
        y = sum(r["vote"] == "yes" for r in att)
        n = sum(r["vote"] == "no" for r in att)
        a = sum(r["vote"] == "abstain" for r in att)
        exp = [int(p) for p in parts]
        if y != exp[0] or n != exp[1] or (len(exp) > 2 and a != exp[2]):
            mismatch.append((mid, f"tally {tally} vs got {y}-{n}-{a}"))
    check("EVERY attributed vote reconciles with the printed tally", mismatch)

    # ---- 4. coverage / sanity (not pass/fail, informational) ----
    motions = len(by_motion)
    attributed_motions = sum(1 for r in by_motion.values() if any(x["councilor"] for x in r))
    movers = sum(1 for r in by_motion.values() if r[0].get("mover"))
    cov = {
        "distinct_motions": motions,
        "attributed_motions": attributed_motions,
        "non_attributable_motions": motions - attributed_motions,
        "attributed_ballots": sum(1 for x in b if x["councilor"]),
        "councilors": len(canon),
        "motions_with_mover": movers,
    }

    # ---- report ----
    print("=" * 64)
    print("votes.json validation")
    print("=" * 64)
    failed = 0
    for name, nfail, sample in results:
        status = "PASS" if nfail == 0 else f"FAIL ({nfail})"
        if nfail:
            failed += 1
        if nfail or not quiet:
            print(f"  [{status:>9}]  {name}")
            if nfail and sample:
                for s in sample:
                    print(f"               e.g. {s}")
    print("-" * 64)
    print("coverage:", json.dumps(cov))
    print("-" * 64)
    if failed:
        print(f"RESULT: {failed} check(s) FAILED")
        sys.exit(1)
    print(f"RESULT: all {len(results)} checks passed ✓")

if __name__ == "__main__":
    main()
