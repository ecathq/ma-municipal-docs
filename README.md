# ma-municipal-docs

Markdown archive of Amherst, MA municipal meeting records — minutes, votes, agendas, and executive-session minutes — scraped daily from amherstma.gov to power a civic chat tool for Amherst residents.

## What's inside
amherst/
├── minutes/                     Approved Town Council Minutes
├── votes/                       Unofficial Record of Votes
├── agendas/                     Town Council Agendas
└── executive-session-minutes/   Executive Session Minutes (Approved & Released)

Each file is one meeting's document, saved as markdown with a metadata header (document type, meeting date, source PDF URL, fetched timestamp) followed by the full extracted text of the PDF.

Filenames sort chronologically: `YYYY-MM-DD-adid<N>-<slug>.md` where `<N>` is the stable Archive Document ID from the town's CivicPlus system.

## How it's updated

A daily job fetches each archive listing, downloads any new PDFs, extracts their text, and commits the new markdown files. Idempotent — only downloads what it hasn't already saved.

Latency from real-world meeting to file in this repo:

| Document | When it lands here |
|---|---|
| Agendas | A few days before the meeting |
| Unofficial Record of Votes | ~1 day after the meeting |
| Approved Minutes | 2–4 weeks after the meeting (once the Council approves them) |
| Executive Session Minutes | Irregular — released after legal review |

## Source

All documents come from the official Town of Amherst website: https://www.amherstma.gov/3435/Town-Council. Each markdown file links back to its original PDF. These are public records under Massachusetts public records law — this repo just mirrors them in a format that's friendlier to retrieval and search.

This is an independent civic project, not affiliated with the Town of Amherst.

If you're the Town Clerk and something here looks wrong, please open an issue.
