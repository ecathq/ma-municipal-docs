#!/usr/bin/env python3
"""
check_gold.py — measure votes.json accuracy against a HUMAN-verified gold set.

This is proof #2: ground truth. validate_votes.py proves the extraction is
self-consistent (reconciles with the printed tally); it cannot prove the
extraction matches the original PDF. Only a human comparing to the PDF can. This
script turns that human check into a reproducible, number-backed result.

Workflow:
  1. Open eval/votes-gold.jsonl. Each line is one sampled motion, pre-filled with
     what the extractor produced (`truth_votes`) plus a `source_pdf` link.
  2. For each row: open the PDF, compare. If the extraction is right, set
     "verified": true. If it's wrong, FIX truth_votes to what the PDF says and
     set "verified": true. Add a note if useful.
  3. Run this script. It compares the CURRENT votes.json against every verified
     row and reports exact-match accuracy with a 95% confidence bound.

    python3 eval/check_gold.py

Exit code is non-zero if any verified row disagrees with votes.json — so once the
gold set is built, regressions are caught automatically in CI.
"""
import json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
GOLD = os.path.join(os.path.dirname(__file__), "votes-gold.jsonl")
VOTES = os.path.join(ROOT, "amherst", "votes.json")

def current_votes(ballots):
    m = defaultdict(dict)
    for x in ballots:
        if x["councilor"]:
            m[x["motion_id"]][x["councilor"]] = x["vote"]
    return m

def main():
    ballots = json.load(open(VOTES, encoding="utf-8"))["ballots"]
    cur = current_votes(ballots)
    gold = [json.loads(l) for l in open(GOLD, encoding="utf-8") if l.strip()]

    verified = [g for g in gold if g.get("verified")]
    total = len(gold)
    if not verified:
        print(f"No rows verified yet (0/{total}). Open eval/votes-gold.jsonl, check "
              f"each motion against its source_pdf, and set \"verified\": true.")
        sys.exit(0)

    match, mismatches = 0, []
    for g in verified:
        got = cur.get(g["motion_id"], {})
        if got == g["truth_votes"]:
            match += 1
        else:
            mismatches.append((g["motion_id"], g["truth_votes"], got))

    n = len(verified)
    acc = 100 * match / n
    # Rule of three: with 0 failures in n samples, the 95% upper bound on the
    # true error rate is ~3/n. More generally we report the simple point estimate
    # plus the rule-of-three bound when clean.
    print("=" * 60)
    print("Ground-truth accuracy vs human-verified gold set")
    print("=" * 60)
    print(f"  verified motions      : {n} / {total}")
    print(f"  exact match to source : {match} / {n}  ({acc:.1f}%)")
    if not mismatches:
        ub = 3.0 / n * 100
        print(f"  95% confidence        : true error rate < {ub:.1f}% "
              f"(rule of three, 0 failures in {n})")
        print(f"\n  → Verify more motions to tighten the bound "
              f"(e.g. 60 clean ⇒ <5%, 100 clean ⇒ <3%).")
    else:
        print(f"\n  {len(mismatches)} MISMATCH(es) — extraction disagrees with your gold:")
        for mid, truth, got in mismatches[:10]:
            print(f"    {mid}\n      gold: {truth}\n      got : {got}")
    print("=" * 60)
    sys.exit(1 if mismatches else 0)

if __name__ == "__main__":
    main()
