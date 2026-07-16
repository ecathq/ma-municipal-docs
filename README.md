# ma-municipal-docs

A public archive of Amherst, MA municipal meeting records — minutes, votes,
agendas, and executive-session minutes — scraped daily from amherstma.gov, **plus
the structured vote dataset (`amherst/votes.json`) built from them.**

This repo is the corpus and the code that produces and checks it. The visual
data explorer that presents this data to residents is a separate, reusable
open-source project — see [The explorer](#the-explorer).

## What's in this repo

```
amherst/                     the scraped corpus (one markdown file per meeting)
  ├── minutes/               Approved Town Council Minutes
  ├── votes/                 Unofficial Record of Votes
  ├── agendas/               Town Council Agendas
  ├── executive-session-minutes/
  └── votes.json             structured vote data, generated from votes/ (see below)
scrape_amherst_minutes.py    the scraper
build_votes_dataset.py       votes/*.md → amherst/votes.json
validate_votes.py            data-invariant checks on votes.json
daily_update.sh              scrape → rebuild votes.json → commit → push
```

## The corpus

Each file is one meeting's document, saved as markdown with a metadata header
(document type, meeting date, source PDF URL, fetched timestamp) followed by the
full extracted text of the PDF. Filenames sort chronologically:
`YYYY-MM-DD-adid<N>-<slug>.md`, where `<N>` is the stable Archive Document ID from
the town's CivicPlus system. A daily job downloads only new PDFs (idempotent).

| Document | When it lands here |
|---|---|
| Agendas | A few days before the meeting |
| Unofficial Record of Votes | ~1 day after the meeting |
| Approved Minutes | 2–4 weeks after the meeting (once the Council approves them) |
| Executive Session Minutes | Irregular — released after legal review |

## The structured vote data — `amherst/votes.json`

`build_votes_dataset.py` parses the `votes/` markdown into a flat dataset: **one
row per councilor per motion** (yes / no / abstain / absent), plus who moved and
seconded each motion, the tally, and a source-PDF link.

The one guarantee: **every attributed vote reconciles exactly with the official
printed tally.** Motions where the record doesn't list per-name votes are marked
non-attributable and left out rather than guessed. The output is deterministic —
it changes only when the underlying records change.

```bash
python3 build_votes_dataset.py     # regenerate amherst/votes.json
```

## Quality checks

The vote data is deterministic, so it's checked with invariants — no LLM needed.
The headline guarantee is that every attributed vote reconciles exactly with the
official printed tally.

```bash
python3 validate_votes.py     # data invariants (reconciliation, schema, …)
```

## The explorer

The visual data explorer — a self-contained web page that lets anyone explore
this vote data, with a plain-language guided path and a "build your own view"
mode — lives in its own reusable, town-agnostic open-source project:

**[council-data-explorer](https://github.com/ecathq/council-data-explorer)**

That repo holds the generic engine (template + build script + its own validation
and page checks); this repo is one data source it can be pointed at. The engine
is deliberately neutral: it presents the public record and links every figure
back to the source PDF; it doesn't rank or evaluate anyone.

## Source

All documents come from the official Town of Amherst website —
https://www.amherstma.gov/3435/Town-Council — and each file links back to its
original PDF. These are public records under Massachusetts public records law;
this repo mirrors them in a friendlier format and adds open tooling on top.

An independent civic project, not affiliated with the Town of Amherst. If you're
the Town Clerk and something here looks wrong, please open an issue.

## License

Code (scraper, structured-data build, and validation) is licensed under the GNU
General Public License v3.0 — see `LICENSE`. Anyone can use, study, and adapt it,
and derivative works stay open too. (The explorer engine is under the same
license in its own repo.)

The ingested corpus of municipal meeting records is publicly available (public
records under Massachusetts law), not owned by this project.

Copyright (c) 2026 CivicSense, Inc.
