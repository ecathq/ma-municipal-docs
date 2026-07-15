#!/usr/bin/env python3
"""
build_votes_dataset.py — structured roll-call layer for ma-municipal-docs.

Reads the markdown in amherst/votes/ (Unofficial Record of Votes) and emits
amherst/votes.json: a flat array of *ballots* (one councilor's vote on one
motion) plus motion-level context. This is the aggregation feed the chatbot
can't compute on its own and the data source for json-render views.

Design notes
------------
The records use three notations that drift over time:
  1. inline   : "ROLL CALL VOTE: 12-0-0; Yes Bahl-Milne, No Brewer, ... Yes Schoen"
  2. block    : "ROLL CALL VOTE: 8-5\nAye: ...\nNay: ...\nPresent (abstain): ...\nAbsent: ..."
  3. unanimous: "ROLL CALL VOTE: Unanimous"  (expanded against the meeting roster)
Plain tallies with no names (e.g. "VOTED: 6-6-0;" with nothing after) are kept
at the motion level but marked non_attributable so nothing is silently dropped.

Attribution is roster-driven: we match votes against the meeting's own
present/remote/absent roster, which cleanly handles multi-word surnames
("De Angelis", "Bahl-Milne", "Devlin Gauthier").

Stdlib only. Python 3.9+.
"""
import re, glob, json, os, sys
from datetime import datetime, timezone

VOTES_DIR = os.path.join(os.path.dirname(__file__), "amherst", "votes")
OUT_PATH  = os.path.join(os.path.dirname(__file__), "amherst", "votes.json")

# --- topic tagging: matched against MOTION TEXT ONLY (not the whole chunk) ---
TOPIC_RULES = {
    "jones-library":        [r"jones library"],
    "schools":             [r"regional school", r"\bschool district\b", r"\belementary school"],
    "budget-appropriation": [r"appropriat", r"\bborrowing order\b", r"transfer order", r"\bbudget\b"],
    "zoning":               [r"\bzoning\b", r"\bMGL Ch\.? *40A\b", r"\bbylaw\b.*zon"],
    "cpa":                  [r"community preservation", r"\bCPA\b", r"\bCPAC\b"],
    "appointments":         [r"\bappoint", r"\breappoint", r"\bnomination\b"],
    "climate-energy":       [r"\benergy\b", r"\bclimate\b", r"\bsolar\b"],
    "rules-procedure":      [r"rules of procedure", r"\brule \d"],
    "resolution":           [r"\bresolution\b", r"\bproclamation\b"],
}

ROSTER_LABEL = re.compile(
    r"^(?P<kind>Members Present|Councilors present|Members Absent|Councilors absent|"
    r"Members Participating Remotely|Councilors participating remotely)\s*:\s*(?P<names>.*)$",
    re.I)
# a line that starts a *new* section, ending a wrapped roster list
NEW_SECTION = re.compile(
    r"^\s*(Members |Councilors |Staff |Non-Voting|President\b|Ms\.|Mr\.|Mayor|"
    r"When remote|\d+\.|[A-Za-z]\.\s|\(|UNOFFICIAL|Town of|$)")

# clean a roster fragment into surnames
def split_names(blob):
    blob = re.sub(r"\(.*?\)", "", blob)                 # drop "(joined at 6:35)"
    blob = re.sub(r"\bCouncilors?\b|\bPresident\b", "", blob, flags=re.I)
    parts = re.split(r",|\band\b|;", blob)
    out = []
    for p in parts:
        n = p.strip().strip(".").strip()
        if not n or n.lower() in ("none", "n/a"):
            continue
        # must look like a surname: 1-3 capitalized words, letters/hyphen/apostrophe
        if not re.fullmatch(r"[A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+){0,2}", n):
            continue
        if len(n) > 22:
            continue
        if re.search(r"\b(present|absent|remote|staff|manager|clerk|director|town|"
                     r"council|none|members|councilors)\b", n, re.I):
            continue
        out.append(n)
    return out

def parse_roster(text):
    present, remote, absent = [], [], []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = ROSTER_LABEL.match(line)
        if not m:
            continue
        blob = m.group("names")
        # absorb at most 2 wrapped continuation lines
        for nxt in lines[i + 1:i + 3]:
            if NEW_SECTION.match(nxt):
                break
            blob += " " + nxt
        kind = m.group("kind").lower()
        names = split_names(blob)
        if "absent" in kind:        absent = names
        elif "remot" in kind:       remote = names
        else:                       present = names
    voting = []
    for n in present + remote:
        if n not in voting:
            voting.append(n)
    return voting, absent

# global canonical councilor list (built in pass 1). Real councilors recur on
# many rosters; one-off staff/guest leaks appear in only one or two files, so a
# document-frequency floor cleans the dimension.
def build_canon(files, min_files=3):
    from collections import Counter
    freq = Counter()
    for f in files:
        txt = open(f, encoding="utf-8").read()
        voting, absent = parse_roster(txt)
        for n in set(voting) | set(absent):
            freq[n] += 1
    keep = {c for c, k in freq.items() if k >= min_files and len(c) > 1}
    # longest first so "De Angelis" matches before "De"
    return sorted(keep, key=lambda c: (-len(c), c))   # longest-first, then alpha (deterministic)

def topic_tags(motion_text):
    t = motion_text.lower()
    tags = [tag for tag, pats in TOPIC_RULES.items()
            if any(re.search(p, t, re.I) for p in pats)]
    return tags

def normalize_name(text, canon):
    """Map a free-text 'Motion by:' value to a canonical councilor surname, or
    None if it isn't a known councilor (e.g. a committee chair or staffer)."""
    if not text:
        return None
    raw = re.sub(r"\(.*?\)", "", text)
    raw = re.sub(r"\b(Councilor|President|Vice|Chair|Mr|Ms|Mrs)\b\.?", "", raw, flags=re.I).strip(" .,;")
    for c in canon:  # canon is longest-first
        if raw.lower() == c.lower() or raw.lower().endswith(c.lower()):
            return c
    return None

VOTE_TOKEN = {"yes": "yes", "aye": "yes", "no": "no", "nay": "no",
              "abstain": "abstain", "abstained": "abstain",
              "absent": "absent", "present": "abstain"}

def parse_block(chunk, voting, absent):
    """block format with Aye:/Nay:/Present (abstain):/Absent: lines."""
    out = {}
    fields = [(r"Aye", "yes"), (r"Nay", "no"),
              (r"Present \(abstain\)", "abstain"), (r"Absent", "absent")]
    saw = False
    for label, vote in fields:
        m = re.search(label + r":\s*(.+)", chunk)
        if not m:
            continue
        saw = True
        for n in split_names(m.group(1)):
            match = next((c for c in voting + absent if c.lower() == n.lower()
                          or c.lower().endswith(n.lower()) or n.lower().endswith(c.lower())), None)
            if match:
                out[match] = vote
    return out if saw else None

def parse_named(seg, canon):
    """inline 'Yes Bahl-Milne, No Brewer, ... abstain Schoen' plus 'Name Abstained'
    suffix. Longest names consumed first so 'De Angelis' wins over 'De'."""
    out, work = {}, " " + seg + " "
    for name in canon:                       # canon is sorted longest-first
        m = re.search(r"(Yes|No|Aye|Nay|abstain|Abstain|absent|Absent)\s+"
                      + re.escape(name) + r"\b", work)
        if m:
            out[name] = VOTE_TOKEN[m.group(1).lower()]
            work = work[:m.start()] + " " * (m.end() - m.start()) + work[m.end():]
            continue
        m = re.search(re.escape(name) + r"\s+Abstain", work)
        if m:
            out[name] = "abstain"
            work = work[:m.start()] + " " * (m.end() - m.start()) + work[m.end():]
    return out

def parse_exceptions(seg, canon, voting, absent):
    """exception form: 'VOTED: 11-0-1 (Councilor DuMont Abstained; Bahl-Milne was
    absent)'. Everyone present defaults to yes; named exceptions override."""
    out = {n: "yes" for n in voting}
    for n in absent:
        out[n] = "absent"
    low = seg.lower()
    for name in canon:
        nl = name.lower()
        for m in re.finditer(re.escape(nl), low):
            a, b = max(0, m.start() - 28), min(len(low), m.end() + 28)
            win = low[a:b]
            if re.search(r"was absent|were absent|\babsent\b", win):
                out[name] = "absent"
            elif "abstain" in win:
                out[name] = "abstain"
            elif re.search(r"\bno\b|opposed|voted against", win):
                out[name] = "no"
    return out

TALLY_RE = re.compile(r"\b(\d{1,2})\s*-\s*(\d{1,2})(?:\s*-\s*(\d{1,2}))?\b")

def counts(per):
    c = {"yes": 0, "no": 0, "abstain": 0}
    for v in per.values():
        if v in c:
            c[v] += 1
    return c["yes"], c["no"], c["abstain"]

def matches_tally(per, tally):
    """does a per-councilor dict reconcile with a 'Y-N' or 'Y-N-A' tally?"""
    if not tally:
        return False
    parts = [int(p) for p in tally.split("-")]
    y, n, a = counts(per)
    if len(parts) == 2:
        return y == parts[0] and n == parts[1]
    return y == parts[0] and n == parts[1] and a == parts[2]

def extract_file(path, canon):
    fname = os.path.basename(path)
    date = fname[:10]
    adid_m = re.search(r"adid(\d+)", fname)
    adid = int(adid_m.group(1)) if adid_m else None
    txt = open(path, encoding="utf-8").read()
    voting, absent = parse_roster(txt)
    canon_set = set(canon)
    voting = [n for n in voting if n in canon_set]
    absent = [n for n in absent if n in canon_set]
    src = re.search(r"Source PDF:\s*(\S+)", txt)
    src = src.group(1) if src else None

    ballots = []
    # split on motion starts
    chunks = re.split(r"(?=^\s*(?:MOVED|MOTION)\b)", txt, flags=re.M)
    midx = 0
    for ch in chunks:
        if not re.match(r"\s*(MOVED|MOTION)\b", ch):
            continue
        midx += 1
        mt = re.search(r"(?:MOVED|MOTION)[^:]*:\s*(.+?)(?:\n\s*(?:Motion by|Seconded by|ROLL CALL|VOTED|VOTE)\b|\Z)",
                       ch, re.S)
        motion_text = re.sub(r"\s+", " ", mt.group(1)).strip() if mt else ""
        motion_id = f"{date}-adid{adid}-m{midx}"
        tags = topic_tags(motion_text)

        # motion sponsorship: who moved it, who seconded it
        bm = re.search(r"Motion by:\s*([^\n]+)", ch)
        sm = re.search(r"Seconded by:\s*([^\n]+)", ch)
        mover = normalize_name(bm.group(1), canon) if bm else None
        seconder = normalize_name(sm.group(1), canon) if sm else None

        # result line: first ROLL CALL/VOTED/VOTE occurrence and its trailing text
        res = re.search(r"(ROLL CALL VOTE|2/3 VOTE|VOTED|VOTE)\s*[^\n:]*:?\s*(.*?)(?:\n\n|\Z)",
                        ch, re.S)
        method = "unknown"; tally = None; per = {}
        if res:
            head = res.group(0)
            unanimous = bool(re.search(r"unanimous", head, re.I))
            roll = bool(re.search(r"ROLL CALL", head, re.I))
            tm = TALLY_RE.search(head)
            if tm:
                tally = "-".join(g for g in tm.groups() if g is not None)

            # Try strategies in priority order; accept the first that reconciles
            # with the printed tally. If a strategy produces names but doesn't
            # reconcile, we keep looking, then fall back to best-effort.
            candidates = []  # (method, per_dict)
            blk = parse_block(ch, voting, absent)
            if blk:
                candidates.append(("roll_call", blk))
            named = parse_named(head, canon)
            if named:
                m = "roll_call" if roll else "voice_named"
                full = dict(named)
                for n in absent:
                    full.setdefault(n, "absent")
                candidates.append((m, full))
            if unanimous:
                u = {n: "yes" for n in voting}
                u.update({n: "absent" for n in absent})
                candidates.append(("unanimous", u))
            if tm:
                candidates.append(("voice_expanded",
                                   parse_exceptions(head, canon, voting, absent)))
                if (tm.group(2) in (None, "0")) and (tm.group(3) in (None, "0")):
                    z = {n: "yes" for n in voting}
                    z.update({n: "absent" for n in absent})
                    candidates.append(("voice_unanimous", z))

            # Only attribute individual votes when they reconcile EXACTLY with the
            # printed tally. Unreconciled motions are kept as motion-level stubs so
            # nothing is silently dropped, but no guessed ballots are emitted.
            chosen = next((c for c in candidates if matches_tally(c[1], tally)), None)
            if chosen:
                method, per = chosen
            else:
                method = "non_attributable"

        if not per:
            # record a motion-level stub so non-attributable votes aren't dropped
            ballots.append({
                "councilor": None, "vote": None, "date": date, "meeting_adid": adid,
                "motion_id": motion_id, "motion_text": motion_text, "topic_tags": tags,
                "tally": tally, "vote_method": method, "source_pdf": src,
                "mover": mover, "seconder": seconder,
            })
            continue
        for councilor, vote in sorted(per.items()):   # deterministic ballot order
            ballots.append({
                "councilor": councilor, "vote": vote, "date": date, "meeting_adid": adid,
                "motion_id": motion_id, "motion_text": motion_text, "topic_tags": tags,
                "tally": tally, "vote_method": method, "source_pdf": src,
                "mover": mover, "seconder": seconder,
            })
    return ballots

def main():
    files = sorted(glob.glob(os.path.join(VOTES_DIR, "*.md")))
    canon = build_canon(files)
    all_ballots = []
    for f in files:
        all_ballots.extend(extract_file(f, canon))

    attributable = [b for b in all_ballots if b["councilor"]]
    # NOTE: deterministic output — no wall-clock timestamp. votes.json changes
    # only when the underlying corpus changes, so the daily job commits/pushes
    # (and CI rebuilds the explorer) only on real data changes, never on no-op days.
    newest = max((b["date"] for b in all_ballots), default=None)
    payload = {
        "meta": {
            "newest_meeting": newest,
            "source_files": len(files),
            "total_records": len(all_ballots),
            "attributable_ballots": len(attributable),
            "non_attributable_motions": len(all_ballots) - len(attributable),
            "grain": "one councilor's vote on one motion",
            "vote_values": ["yes", "no", "abstain", "absent"],
            "vote_methods": ["roll_call", "unanimous", "voice_unanimous",
                             "voice_named", "non_attributable", "unknown"],
        },
        "ballots": all_ballots,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(json.dumps(payload["meta"], indent=2))

if __name__ == "__main__":
    main()
