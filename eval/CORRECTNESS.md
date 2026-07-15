# Proving the data is correct

"Correct" splits into two claims that need two different proofs. Be precise about
which one you're making.

## Proof #1 — self-consistency  (deterministic, 100% coverage, already done)

**Claim:** every vote the tool attributes to a councilor matches the *official
printed tally* for that motion.

**Proof:** `validate_votes.py` recomputes, for all 508 attributed motions, the
yes/no/abstain counts from the individual votes and requires them to equal the
tally printed in the record. It passes on 508/508 — i.e. **6,591 individual
councilor-votes** all reconcile. Motions where the record doesn't list per-name
votes (1,243 of them) are marked non-attributable and left out rather than
guessed. This is reproducible (`python3 validate_votes.py`, exits 0) and the code
is the evidence.

**What this rules out:** a swapped or invented yes/no/abstain — because it would
change the counts and fail reconciliation. A wrong per-councilor vote cannot ship.

**What it does NOT prove:** that `votes.json` matches the original PDF. Bad text
extraction that still happens to add up (e.g. a mis-read surname, or an error
already in the source tally) would pass. Reconciliation is necessary, not
sufficient.

Also proven deterministically: **the page shows exactly what `votes.json` says** —
`node eval/test_page.js` recounts independently and matches every figure.

## Proof #2 — ground truth  (human-verified sample, gives an accuracy number)

You cannot *prove* 100% ground-truth correctness of 1,751 motions without reading
all 1,751 PDFs. What you CAN do — and what's defensible for release — is **measure**
accuracy on a random sample and state it with a confidence bound.

**Method (`eval/votes-gold.jsonl` + `eval/check_gold.py`):**
1. `votes-gold.jsonl` holds 30 randomly-sampled motions, each pre-filled with what
   the extractor produced and a link to its source PDF.
2. For each, open the PDF and compare. If right, set `"verified": true`. If wrong,
   correct `truth_votes` to what the PDF says and set `"verified": true`.
3. `python3 eval/check_gold.py` compares `votes.json` to your verified truth and
   reports exact-match accuracy + a 95% bound.

**The statistics (rule of three):** if you verify *n* motions and find **0**
errors, you can state with 95% confidence that the true error rate is below
**3/n**. So:
- 30 clean  ⇒  error rate < 10%
- 60 clean  ⇒  error rate < 5%
- 100 clean ⇒  error rate < 3%

Pick the bound you're comfortable releasing on and verify that many. This is the
number you put in a "how we check the data" note: *"We hand-checked N motions
against the town's PDFs; all matched; measured error rate below X%."*

**Bonus — it becomes a regression test.** Once verified, the gold set is committed,
and `check_gold.py` fails CI if any future build ever disagrees with it. So the
sample you audit once keeps proving itself on every rebuild.

## Summary

| Claim | Proof | Status |
|---|---|---|
| Attributed votes match the printed tally | `validate_votes.py` (508/508) | done, reproducible |
| Page matches votes.json | `eval/test_page.js` | done, reproducible |
| votes.json matches the source PDFs | `check_gold.py` over verified `votes-gold.jsonl` | **needs your audit pass** |

The first two are machine-proven and in CI. The third is the one that needs a
human afternoon with the PDFs — after which you have a hard accuracy number, not a
claim.
