#!/usr/bin/env python3
"""
Scrape Amherst, MA Town Council documents (approved minutes, unofficial
record of votes, agendas, executive-session minutes) from the town's
CivicPlus archive and save each one as a markdown file.

Source listings (all use the same `Archive.aspx?AMID=N` layout):
    AMID=206  Approved Town Council Minutes
    AMID=223  Unofficial Record of Votes
    AMID=204  Agendas
    AMID=236  Approved & Released Executive Session Minutes

Each archive entry link (`Archive.aspx?ADID=M`) redirects to the actual PDF.
We follow it with a single HTTP GET and keep both the PDF bytes and the
`Content-Disposition` filename returned by the server — the filename
reliably contains the meeting date even when the listing text does not.

The script is idempotent: each run skips entries whose markdown file
already exists, so it's safe on a daily schedule.

Usage:
    python scrape_amherst_minutes.py                 # all archives, all new entries
    python scrape_amherst_minutes.py --archive votes # only one archive type
    python scrape_amherst_minutes.py --limit 5       # stop after 5 new downloads
    python scrape_amherst_minutes.py --latest-only   # only the newest entry in each archive
    python scrape_amherst_minutes.py --dry-run       # list entries, don't download

Environment:
    AMHERST_OUTPUT_DIR   Override base output directory (default: ./ next to this script)
"""

from __future__ import annotations

import argparse
import html
import io
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import pdfplumber
import requests

BASE = "https://www.amherstma.gov"

# Top-level directory for this town — lets the repo hold other MA towns
# later (northampton/, easthampton/, etc.) without restructuring.
TOWN = "amherst"

# Archive type config: slug -> (AMID, listing-friendly name, subfolder).
# Final on-disk path is {OUTPUT_DIR}/{TOWN}/{subfolder}/.
ARCHIVES: dict[str, dict] = {
    "minutes": {
        "amid": 206,
        "label": "Approved Town Council Minutes",
        "subfolder": "minutes",
    },
    "votes": {
        "amid": 223,
        "label": "Unofficial Record of Votes",
        "subfolder": "votes",
    },
    "agendas": {
        "amid": 204,
        "label": "Town Council Agendas",
        "subfolder": "agendas",
    },
    "executive-session": {
        "amid": 236,
        "label": "Executive Session Minutes (Approved & Released)",
        "subfolder": "executive-session-minutes",
    },
}

ARCHIVE_LISTING_URL = BASE + "/Archive.aspx?AMID={amid}"
ARCHIVE_ITEM_URL = BASE + "/Archive.aspx?ADID={adid}"

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.environ.get("AMHERST_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))

USER_AGENT = (
    "AmherstCouncilScraper/1.0 "
    "(civic-transparency project; contact: amherst resident)"
)

# ---------- logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("amherst-scraper")


# ---------- listing parser ----------

ENTRY_RE = re.compile(
    r'<a\s+href="Archive\.aspx\?ADID=(?P<adid>\d+)"[^>]*>\s*'
    r'\s*<span>(?P<title>[^<]+)</span>',
    re.IGNORECASE,
)

# Matches "MM-DD-YYYY" anywhere in a title string
DATE_IN_TEXT_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
# Matches "MM-DD-YY" (2-digit year) — some filenames use this
DATE_SHORT_RE = re.compile(r"\b(\d{2})-(\d{2})-(\d{2})\b")


def extract_date(*texts: str) -> datetime | None:
    """Try each text in order; return the first parseable MM-DD-YYYY date."""
    for text in texts:
        if not text:
            continue
        m = DATE_IN_TEXT_RE.search(text)
        if m:
            mm, dd, yyyy = m.groups()
            try:
                return datetime(int(yyyy), int(mm), int(dd))
            except ValueError:
                pass
        # Try MM-DD-YY fallback (assume 20YY)
        m = DATE_SHORT_RE.search(text)
        if m:
            mm, dd, yy = m.groups()
            try:
                return datetime(2000 + int(yy), int(mm), int(dd))
            except ValueError:
                pass
    return None


def fetch_listing(amid: int) -> str:
    url = ARCHIVE_LISTING_URL.format(amid=amid)
    log.info("Fetching archive listing: %s", url)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_listing(page_html: str) -> list[dict]:
    entries: list[dict] = []
    seen_adids: set[str] = set()

    for m in ENTRY_RE.finditer(page_html):
        adid = m.group("adid")
        if adid in seen_adids:
            continue
        seen_adids.add(adid)

        title_raw = html.unescape(m.group("title")).strip()
        entries.append(
            {
                "adid": adid,
                "title": title_raw,
                "pdf_url": ARCHIVE_ITEM_URL.format(adid=adid),
            }
        )
    return entries


# ---------- download + text extraction ----------

def slugify(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:max_len].strip("-")


def output_path_for(entry: dict, archive_dir: Path) -> Path:
    """Use ADID-only filenames for a stable, idempotent check BEFORE we know
    the date. We'll rename to a dated filename after the first download."""
    return archive_dir / f"adid-{entry['adid']}.md"


def existing_dated_path(entry: dict, archive_dir: Path) -> Path | None:
    """Find any already-saved file for this ADID (by the 'adidN' token in name)."""
    for p in archive_dir.glob(f"*adid{entry['adid']}*.md"):
        return p
    for p in archive_dir.glob(f"adid-{entry['adid']}.md"):
        return p
    return None


def download_pdf(url: str) -> tuple[bytes, str | None]:
    """Return (pdf_bytes, server_filename_or_None)."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60,
                        allow_redirects=True)
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "")
    if "pdf" not in ctype.lower() and not resp.content.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF at {url}, got Content-Type={ctype!r}")

    filename = None
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*=UTF-8\'\'([^;]+)|filename="?([^";]+)"?', cd)
    if m:
        filename = unquote(m.group(1) or m.group(2) or "").strip()

    return resp.content, filename


def pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text = re.sub(r"[ \t]+\n", "\n", text)
            pages.append(text.strip())
    return "\n\n---\n\n".join(p for p in pages if p)


def build_markdown(entry: dict, archive_label: str, meeting_date: datetime | None,
                   server_filename: str | None, body_text: str) -> str:
    date_str = meeting_date.date().isoformat() if meeting_date else "(date unknown)"
    header_title = server_filename or entry["title"]
    header = (
        f"# {header_title}\n\n"
        f"- Document type: {archive_label}\n"
        f"- Meeting date: {date_str}\n"
        f"- Listing title: {entry['title']}\n"
        f"- Source PDF: {entry['pdf_url']}\n"
        f"- Fetched: {datetime.utcnow().isoformat(timespec='seconds')}Z\n\n"
        "---\n\n"
    )
    return header + body_text.strip() + "\n"


# ---------- per-archive main ----------

def process_archive(slug: str, cfg: dict, args: argparse.Namespace,
                    counts: dict[str, int]) -> None:
    archive_dir = OUTPUT_DIR / TOWN / cfg["subfolder"]
    archive_dir.mkdir(parents=True, exist_ok=True)
    log.info("=== Archive: %s  ->  %s", cfg["label"], archive_dir)

    page_html = fetch_listing(cfg["amid"])
    entries = parse_listing(page_html)
    log.info("Listing has %d entries", len(entries))

    if args.latest_only:
        entries = entries[:1]

    new_this_archive = 0
    for entry in entries:
        # Skip if we already have a file for this ADID (regardless of name)
        if existing_dated_path(entry, archive_dir):
            counts["skip"] += 1
            continue

        if args.dry_run:
            log.info("[dry-run] would fetch ADID %s: %s",
                     entry["adid"], entry["title"])
            counts["new"] += 1
            continue

        log.info("Downloading: %s (ADID %s)", entry["title"], entry["adid"])
        try:
            pdf_bytes, server_fn = download_pdf(entry["pdf_url"])
            text = pdf_bytes_to_text(pdf_bytes)
            meeting_date = extract_date(entry["title"], server_fn or "")
            if not meeting_date:
                log.warning("Couldn't parse meeting date for ADID %s (title=%r, file=%r)",
                            entry["adid"], entry["title"], server_fn)

            # Filename: YYYY-MM-DD-adidN-slug.md (or no date prefix if unknown)
            base_slug = slugify((server_fn or entry["title"]).rsplit(".", 1)[0])
            if meeting_date:
                fname = f"{meeting_date.date().isoformat()}-adid{entry['adid']}-{base_slug}.md"
            else:
                fname = f"undated-adid{entry['adid']}-{base_slug}.md"
            out_path = archive_dir / fname

            md = build_markdown(entry, cfg["label"], meeting_date, server_fn, text)
            out_path.write_text(md, encoding="utf-8")
            log.info("Saved: %s", out_path.name)
            counts["new"] += 1
            new_this_archive += 1
            time.sleep(0.5)  # polite

            if args.limit and counts["new"] >= args.limit:
                log.info("Reached --limit %d, stopping.", args.limit)
                return
        except Exception as exc:
            log.error("Failed ADID %s: %s", entry["adid"], exc)
            counts["error"] += 1

    log.info("Archive %s: %d new", slug, new_this_archive)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape Amherst, MA Town Council archives.")
    p.add_argument("--archive", choices=list(ARCHIVES.keys()) + ["all"], default="all",
                   help="Which archive to scrape (default: all).")
    p.add_argument("--limit", type=int, default=0,
                   help="Stop after downloading N new entries across all archives (0 = no limit).")
    p.add_argument("--latest-only", action="store_true",
                   help="Only process the single newest entry in each archive.")
    p.add_argument("--dry-run", action="store_true",
                   help="List entries that would be downloaded, but do not fetch PDFs.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Base output directory: %s", OUTPUT_DIR)

    selected = list(ARCHIVES.keys()) if args.archive == "all" else [args.archive]
    counts = {"new": 0, "skip": 0, "error": 0}

    for slug in selected:
        try:
            process_archive(slug, ARCHIVES[slug], args, counts)
        except Exception as exc:
            log.error("Archive %s failed entirely: %s", slug, exc)
            counts["error"] += 1
        if args.limit and counts["new"] >= args.limit:
            break

    log.info("Done. new=%d skip=%d error=%d",
             counts["new"], counts["skip"], counts["error"])
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
