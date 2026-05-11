# Amherst Council Docs — Roadmap

A chat-with-your-town-council corpus scraped daily from [amherstma.gov](https://www.amherstma.gov).

## What's in the corpus

Daily scrape of four Archive.aspx feeds into `minutes/`, `votes/`, `agendas/`, and `executive-session-minutes/`. Each meeting becomes one markdown file with a metadata header (document type, meeting date, source PDF URL, fetched timestamp) followed by full extracted text. Idempotent — safe to re-run. Runs on a scheduled GitHub Actions workflow.

| Archive | Source (AMID) | Typical latency |
|---|---|---|
| Approved Minutes | 206 | 2–4 weeks after meeting |
| Unofficial Record of Votes | 223 | ~1 day after meeting |
| Agendas | 204 | A few days before meeting |
| Executive Session Minutes | 236 | Irregular — released after legal review |
