# Evaluating the council-explorer page

This page is deterministic — it only does arithmetic over `votes.json`. So it's
evaluated with **free, no-LLM checks**, not Braintrust or promptfoo. Two scripts
run in under a second and exit non-zero on failure, so they drop straight into
CI or `daily_update.sh`.

(The chatbot is a separate project and is evaluated separately with Braintrust —
nothing here touches it.)

## 1. Is the data right?  →  `validate_votes.py`  (free)

```bash
python3 validate_votes.py
```

11 invariant checks over `votes.json`. The headline one: **every attributed vote
reconciles exactly with the printed tally**. Also checks schema, value domains,
source-URL format, no double-votes, mover/seconder are real councilors, etc.

## 2. Does the page compute & render correctly?  →  `eval/test_page.js`  (free)

```bash
node eval/test_page.js
```

Runs the page's *own* JavaScript headless (tiny DOM stub) and asserts every
figure it would show matches an **independent recount of `votes.json`** — the
vote breakdowns, motions-per-year, top proposer, the "Wrapped" facts, the
click-to-drill record counts — plus that every measure × breakdown × chart and
every guided question × visual renders without error. No browser, no API key.

This is the cheap alternative to an LLM eval: because the page is deterministic,
re-deriving the expected numbers from the source data is both free and stronger
than asking a model to grade it.

## 3. Manual spot-check  →  `eval/votes-audit.html`

Open in a browser. A stratified sample of 27 motions (every year, every
extraction format) shown beside a link to the official amherstma.gov PDF, with
Correct / Issue / Unsure buttons + notes that save in the browser. Use it to eye
a handful against source and to catch extraction *misses* (the not-attributed
cards). Fold any corrections into a permanent gold set over time.

## Optional — topic tags  →  promptfoo  (the only part that costs anything)

`promptfooconfig.yaml` + `topics-tests.yaml`. Topic labels (library, budget,
zoning…) are a fuzzy language judgement, so *if* you want to grade them, an
LLM-as-judge fits. This is **optional** — everything load-bearing in the page is
covered for free by 1–2 above. Run only if you want to measure tag quality or
test an LLM tagger as a replacement for the keyword heuristic:

```bash
cd eval && ANTHROPIC_API_KEY=sk-... npx promptfoo@latest eval
```

Note: the `expected` labels were seeded from the current heuristic — give them a
human pass before trusting the score.
