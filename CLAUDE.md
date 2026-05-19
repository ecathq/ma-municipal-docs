# CLAUDE.md

Context for Claude Code working in this repo. Read this first.

## What this is

`ma-municipal-docs` — a daily-updated markdown corpus of Massachusetts town
government meeting records, scraped from official town websites. The corpus
feeds a chat-with-your-town-council tool hosted on Replit. Currently only
Amherst, MA is wired up; the folder layout is ready for more towns.

- GitHub: <https://github.com/ecathq/ma-municipal-docs>
- Owner: Emma Quigley (`ecathq` on GitHub)
- Public repo — nothing confidential; everything is already public record.

## Repo layout

```
.
├── CLAUDE.md                        # this file
├── README.md                        # public-facing README
├── ROADMAP.md                       # v1/v2 scope
├── requirements.txt                 # Python deps
├── scrape_amherst_minutes.py        # the scraper
├── daily_update.sh                  # wrapper: scrape → commit → push
├── .gitignore
└── amherst/
    ├── minutes/                     # Approved Town Council Minutes (AMID=206)
    ├── votes/                       # Unofficial Record of Votes (AMID=223)
    ├── agendas/                     # Agendas (AMID=204)
    └── executive-session-minutes/   # Exec session, approved & released (AMID=236)
```

Each file is a single meeting. Naming convention:

```
YYYY-MM-DD-adid<N>-<slug>.md
```

`YYYY-MM-DD` is the meeting date, `<N>` is the source ADID (Archive Document
ID from the town's CivicPlus archive — stable and unique per document). The
ADID in the filename is what makes the scraper idempotent: it skips any doc
whose `*adid<N>*.md` already exists.

Every markdown file starts with a metadata header:

```
# <server-reported PDF filename>

- Document type: <archive label>
- Meeting date: YYYY-MM-DD
- Listing title: <text as it appeared on the archive listing>
- Source PDF: https://www.amherstma.gov/Archive.aspx?ADID=<N>
- Fetched: <UTC ISO timestamp>

---

<full extracted text of the PDF, page-separated by `---`>
```

## Source of truth

Town of Amherst Town Council archives. All four feeds use the same
`Archive.aspx?AMID=<N>` layout — pagination isn't needed; the full list
loads in one response. Each archive entry link (`Archive.aspx?ADID=<M>`)
302-redirects to the actual PDF; `Content-Disposition` gives the filename.

| Archive | AMID | Latency | Count (as of initial backfill) |
|---|---|---|---|
| Approved Minutes | 206 | 2–4 weeks after meeting | 293 |
| Unofficial Record of Votes | 223 | ~1 day after meeting | 178 |
| Agendas | 204 | A few days before meeting | 367 |
| Executive Session Minutes | 236 | Irregular (legal review) | 16 |

Packets (staff memos, backup materials) live in a React-driven
DocumentCenter and are deferred to v2 — see ROADMAP.md.

## How to run

```bash
# Install deps (one-time)
pip install -r requirements.txt

# Scrape everything new across all archives
python3 scrape_amherst_minutes.py

# Scrape a single archive
python3 scrape_amherst_minutes.py --archive minutes
python3 scrape_amherst_minutes.py --archive votes
python3 scrape_amherst_minutes.py --archive agendas
python3 scrape_amherst_minutes.py --archive executive-session

# Preview without downloading
python3 scrape_amherst_minutes.py --dry-run

# Just the newest entry in each archive (quick smoke test)
python3 scrape_amherst_minutes.py --latest-only

# Stop after N new downloads
python3 scrape_amherst_minutes.py --limit 5
```

Behavior:

- Idempotent: existing `*adid<N>*.md` files are skipped.
- Polite: 0.5s sleep between downloads.
- Dates are extracted from (1) the listing span text, else (2) the server's
  Content-Disposition filename. If neither has a date, the file gets an
  `undated-adid<N>-...` prefix and logs a warning.

## Daily workflow

`daily_update.sh` is the end-to-end cron-ready entry point:

```bash
./daily_update.sh
```

It runs the scraper, then `git add . && git commit -m ... && git push` if
there are new files. Designed for `launchd`/`cron`. Recommended schedule:
once a day, morning local time (minutes get posted during business hours).

Example `crontab -e` entry (7:00 AM daily):

```
0 7 * * * cd ~/path/to/ma-municipal-docs && ./daily_update.sh >> daily.log 2>&1
```

`daily.log` is gitignored.

## Conventions

- Python 3.9+. Standard library plus `requests` and `pdfplumber`.
- No framework — the scraper is a single file by design. If it grows past
  ~400 lines, split into `scraper/` package before it gets worse.
- Keep filenames date-prefixed so they sort chronologically in any tool.
- Do **not** rewrite existing markdown files. If extraction logic changes,
  version it (new metadata field, new section) rather than silently
  rewriting history. The repo's git log is part of the value.
- Never commit `.env` or anything in `__pycache__/`.

## Adding another Massachusetts town

The scraper currently hardcodes `TOWN = "amherst"`. Pattern for a new town:

1. Find the town's CivicPlus Archive.aspx AMIDs for minutes, votes, etc.
2. Copy `scrape_amherst_minutes.py` to `scrape_<town>.py`, change `TOWN`
   and the `ARCHIVES` dict.
3. Add a `<town>/` folder with the same subfolder layout.
4. Add a line to `daily_update.sh` to also invoke the new scraper.

Long-term: refactor the scraper to accept a town config file so one script
can handle all towns. Holding off on that until we have a second town.

## Gotchas

- The town website occasionally times out individual downloads. The
  scraper logs `ERROR  Failed ADID ...: ... Read timed out` and moves on.
  Because the script is idempotent, the next run will retry those ADIDs
  automatically. No special retry logic needed.
- Executive session minutes have the release date baked into the listing
  title (e.g. "12-06-2021 ... - Approved and released 05-16-2022"). The
  date parser picks the *first* date it finds in the title, which is the
  meeting date — that's the behavior we want.
- Some agendas don't have a date in the listing span; the date always
  appears in the Content-Disposition filename, so the scraper falls back
  to that. If both lack dates, the file is saved with an `undated-` prefix
  and a warning is logged.

## Pointers

- ROADMAP.md — what's v1 vs v2 (packets, other towns, YouTube transcripts)
- README.md — the face of the repo for anyone landing on GitHub

## Replit chat front end (context, not part of this repo)

The Replit app is a separate project. It clones this repo (or pulls the
raw markdown files over HTTPS) and feeds them into a retrieval-augmented
chat interface. Users of the chat can ask "what did the Council decide
about the Jones Library budget?" and get grounded answers with citations
back to the source PDFs on `amherstma.gov`.

Any change to file layout or metadata header format here is a breaking
change for the Replit app's parser. Bump a version note in README.md if
you ever change either.
