# Amherst Council Docs — Roadmap

A chat-with-your-town-council corpus scraped daily from
[amherstma.gov](https://www.amherstma.gov/3435/Town-Council).

## v1 — shipped

Daily scrape of four Archive.aspx feeds into `minutes/`, `votes/`,
`agendas/`, and `executive-session-minutes/`. Each meeting becomes one
markdown file with a metadata header (document type, meeting date,
source PDF URL, fetched timestamp) followed by full extracted text.
Idempotent — safe to re-run. Runs on a scheduled Cowork task.

| Archive | Source (AMID) | Typical latency |
|---|---|---|
| Approved Minutes | 206 | 2–4 weeks after meeting |
| Unofficial Record of Votes | 223 | ~1 day after meeting |
| Agendas | 204 | A few days before meeting |
| Executive Session Minutes | 236 | Irregular — released after legal review |

## v2 — planned

### Meeting Packets

Full backup materials for each meeting: staff memos, draft ordinances,
financial reports, committee recommendations. One big PDF per meeting,
usually 100–300 pages. Published at the same time as agendas.

Why deferred: packets live in a React-driven CivicPlus DocumentCenter
(`/DocumentCenter/Index/8054` and per-year equivalents) instead of the
simple `Archive.aspx` pages. The document list is loaded by a JS API
call that isn't exposed in the initial HTML, so scraping them needs a
headless browser (e.g. Playwright) rather than plain `requests`.

Scope when we tackle v2:

- Headless-browser scraper that enumerates every year's packet folder
  and extracts each packet's documentID, title, posted date, and PDF
  URL.
- Decide on corpus strategy: full-text index (quadruples corpus size,
  adds noise to retrieval) vs. metadata-only index that links out to the
  PDF on amherstma.gov.
- Chunking strategy: packets need aggressive splitting (by agenda item /
  section heading) so retrieval doesn't return 300-page blobs.

### Other candidates for v2

- Other town body minutes (Select Board, Planning Board, School
  Committee) — same Archive.aspx layout, should be a one-line config
  change once we decide which boards to include.
- YouTube meeting videos from
  [@TownofAmherstMA01002](https://www.youtube.com/@TownofAmherstMA01002)
  with auto-transcripts, to cover the gap between meeting and approved
  minutes.
- A small `index.json` summarizing every document (date, type, title,
  path) so the Replit front end can build a timeline view without having
  to re-index the whole corpus.
