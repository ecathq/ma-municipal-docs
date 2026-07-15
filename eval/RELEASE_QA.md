# Release QA — council-explorer page

Run this before putting a new build of `council-explorer.html` live. The goal is
to verify the chain **source PDF → `votes.json` → number on the page** at every
link. Release only when Steps 1–3 are clean.

## 0. Rebuild from source
```bash
python3 build_votes_dataset.py     # regenerate amherst/votes.json
# then regenerate the page from the template (or your build step)
```

## 1. Automated gates — must both exit 0
```bash
python3 validate_votes.py          # 11 data invariants
node eval/test_page.js             # page matches an independent recount
```
- `validate_votes.py` headline check: **every attributed vote reconciles with the
  printed tally** — a wrong per-councilor vote cannot ship.
- `test_page.js` proves the page's figures (breakdowns, per-year counts, top
  proposer, Wrapped facts, drill-down counts) equal a fresh recount of `votes.json`.
- If either fails, stop. Read the failing check; do not release.

## 2. Source spot-check — the "correct data" test  (`eval/votes-audit.html`)
Open it in a browser. For **15–20 motions across different years and formats**:
1. Click **Open official record**, find the motion in the PDF.
2. Confirm the extracted votes / tally / mover match the PDF exactly.
3. Mark Correct / Issue / Unsure; note anything wrong.

Do this deliberately for:
- [ ] 2–3 votes you can independently verify (a recent meeting; a high-profile
      item like a Jones Library borrowing).
- [ ] Several **"not attributed"** cards — confirm the PDF genuinely doesn't list
      per-councilor votes (a true voice vote), rather than an extraction miss.
- [ ] At least one motion from each year, incl. the partial current year.

Example of a clean match (roll-call): `votes.json` YES/NO is character-for-character
identical to the PDF's `Aye:` / `Nay:` lines.

## 3. In-browser smoke test  (the live page)
Open the deployed page in **Chrome, Safari, and on a phone**.
- [ ] Fonts load, layout holds, no errors in the browser console.
- [ ] **End-to-end cross-check ×3–4:** pick a councilor in Explore → note a number
      → click the bar/point → open a record → confirm the vote matches the PDF.
- [ ] Wrapped: the "closest vote", "busiest / most recent decision" each open a
      correct source record.
- [ ] Filters & drill-down: topic filter, councilor filter, chart-type switch,
      "See the actual votes" all behave.
- [ ] Edge cases: a councilor with few votes; a topic with few motions; the
      partial current year is labelled "so far".

## 4. Freshness
- [ ] Newest year and the "most recent decision" match the latest meeting posted
      on amherstma.gov (i.e. the deployed data isn't stale vs the scrape).

## 5. Copy / neutrality read-through
- [ ] Headline and labels stay neutral ("Explore Amherst council data", not
      "voting record"); no councilor singled out in prominent surfaces.
- [ ] Sources & glossary panels read correctly.

## Sign-off
Release when: Step 1 green · Step 2 no unexplained mismatches · Step 3 clean.
Log any Step-2 corrections into a permanent gold set so they're caught
automatically next time.
