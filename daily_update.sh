#!/usr/bin/env bash
# Daily update: scrape Amherst Town Council archives, commit, push.
#
# Intended to be run from cron/launchd. Exits 0 on success (even if
# there was nothing new), non-zero on any failure worth alerting on.

set -euo pipefail

# Always run from the repo root (the directory this script lives in).
cd "$(dirname "$0")"

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily_update starting ==="

# 1. Scrape.
python3 scrape_amherst_minutes.py

# 2. If nothing changed, we're done.
if [ -z "$(git status --porcelain)" ]; then
    echo "No new documents today."
    exit 0
fi

# 3. Commit everything that changed.
git add amherst/
COUNT=$(git diff --cached --name-only | wc -l | tr -d ' ')
MSG="Daily update: $(date -u +%Y-%m-%d) — $COUNT new/changed files"
git commit -m "$MSG"

# 4. Push. Relies on gh/git credentials already being set up on this machine.
git push origin main

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily_update done ($COUNT files) ==="
