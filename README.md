# ma-municipal-docs

A public archive of Amherst, MA municipal meeting records — minutes, votes,
agendas, and executive-session minutes — scraped daily from amherstma.gov, **and
the open-source tooling that turns them into a visual data explorer** for Amherst
residents.

This repo is the *open build*: the corpus, the code that structures it, the
explorer's source, and the quality checks. The explorer's live page is served
from the project's app at **askmytown.org/explore** (see "How it's deployed").

## What's in this repo

```
amherst/                     the scraped corpus (one markdown file per meeting)
  ├── minutes/               Approved Town Council Minutes
  ├── votes/                 Unofficial Record of Votes
  ├── agendas/               Town Council Agendas
  ├── executive-session-minutes/
  └── votes.json             structured vote data, generated from votes/ (see below)
explorer/                    the open-source data explorer
  ├── explorer.template.html the page (design + logic; data is injected at build)
  └── build_explorer.py      injects votes.json into the template → build/index.html
eval/                        quality checks + a viewable QA report
scrape_amherst_minutes.py    the scraper
build_votes_dataset.py       votes/*.md → amherst/votes.json
validate_votes.py            data-invariant checks
daily_update.sh              scrape → rebuild votes.json → commit → push → ingest
.github/workflows/           CI: QA on every push; rebuild+deploy the explorer
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

## The explorer

A single, self-contained web page that lets anyone explore the vote data — a
plain-language guided path for residents and a full "build your own view" mode
for the data-comfortable. It's deliberately neutral: it presents the public
record and links every figure back to the source PDF; it doesn't rank or
evaluate anyone.

It's a **static HTML file with the data embedded** — no backend, no runtime API
calls. Fonts and icons load from public CDNs. To build and preview it yourself:

```bash
python3 build_votes_dataset.py       # 1. structured data
python3 explorer/build_explorer.py   # 2. inject it into the template → build/index.html
open build/index.html                # 3. open in a browser
```

Edit the design/logic in `explorer/explorer.template.html`. The build replaces
the `__M__` / `__B__` / `__META__` placeholders with the data; `build/` is
git-ignored (it's a generated artifact).

## Quality checks (`eval/`)

The vote data is deterministic, so it's checked with invariants and a
human-verified sample — no LLM needed.

```bash
python3 validate_votes.py     # data invariants (reconciliation, schema, …)
node    eval/test_page.js      # the page's numbers match an independent recount
python3 eval/run_qa.py         # runs all of the above + writes eval/qa-report.html
python3 eval/check_gold.py     # accuracy vs a human-verified gold sample
```

See `eval/CORRECTNESS.md` for what is and isn't provable, and `eval/RELEASE_QA.md`
for the pre-release checklist. `eval/promptfooconfig.yaml` is an optional
LLM-as-judge check for the (fuzzy) topic tags.

## How it's deployed

Build in the open here, pull into the controlled app (token-free — no cross-repo
secret lives in this public repo):

1. The daily job rebuilds `votes.json` and pushes it to this repo.
2. `.github/workflows/build-explorer.yml` rebuilds the explorer, gates it on the
   QA checks, and commits the built `explorer/index.html` back to *this* repo
   (open artifact, built from public data) using the built-in `GITHUB_TOKEN`.
3. The app (`ma-municipal-chat`) pulls that public file and serves it at
   **askmytown.org/explore**.

So this public repo is the source of *how the page is made* and holds no
credentials; the page that's actually served is controlled inside the app.
Anyone can reproduce the exact page from this repo with the build commands above.

## Source

All documents come from the official Town of Amherst website —
https://www.amherstma.gov/3435/Town-Council — and each file links back to its
original PDF. These are public records under Massachusetts public records law;
this repo mirrors them in a friendlier format and adds open tooling on top.

An independent civic project, not affiliated with the Town of Amherst. If you're
the Town Clerk and something here looks wrong, please open an issue.

## License

Code (scraper, ingestion pipeline, structured-data build, explorer, and evals) is
licensed under the GNU General Public License v3.0 — see `LICENSE`. Anyone can
use, study, and adapt it, and derivative works stay open too.

The ingested corpus of municipal meeting records is publicly available (public
records under Massachusetts law), not owned by this project.

Copyright (c) 2026 CivicSense, Inc.
