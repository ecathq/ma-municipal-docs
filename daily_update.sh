#!/usr/bin/env bash
# Daily update: scrape Amherst Town Council archives, commit, push,
# then trigger chat-app ingest.
#
# Intended to be run from cron/launchd. Exits 0 on success (even if
# there was nothing new), non-zero on any failure worth alerting on.
#
# Ingest credentials live at ~/.askmytown-admin-creds in netrc format,
# mode 600. File contents:
#     machine askmytown.org
#       login yourusername
#       password yourpassword
# Using --netrc-file (rather than curl -u "user:pass") keeps the
# credentials out of the curl process's argv, so they don't show up
# in `ps` output for other processes running as the same user.
# If the file is missing, the ingest step is skipped with a warning
# (useful for manual runs before credentials are set up).

set -euo pipefail

# Always run from the repo root (the directory this script lives in).
cd "$(dirname "$0")"

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily_update starting ==="

# 1. Scrape.
python3 scrape_amherst_minutes.py

# 2. Commit and push if there are corpus changes. We stage amherst/
#    first and then check whether anything actually got staged — this
#    way, unrelated working-tree changes (like edits to this script
#    itself) don't trigger an empty commit attempt that would fail.
git add amherst/
if ! git diff --cached --quiet; then
    COUNT=$(git diff --cached --name-only | wc -l | tr -d ' ')
    MSG="Daily update: $(date -u +%Y-%m-%d) — $COUNT new/changed files"
    git commit -m "$MSG"
    git push origin main
    echo "Pushed $COUNT files."
else
    echo "No new documents today."
fi

# 3. Trigger chat-app ingest. Runs every day regardless of whether new
#    files were pushed today — this guarantees the chat-app stays
#    current even if a previous day's ingest failed silently.
CREDS_FILE="$HOME/.askmytown-admin-creds"
if [ -f "$CREDS_FILE" ]; then
    echo "Triggering ingest..."
    # Origin header is required because the chat-app does a same-origin
    # check on POSTs and rejects requests without it (403 "Cross-site
    # request blocked"). Long-term fix is to exempt /api/admin/* from
    # that check on the server side since Basic Auth already protects
    # these routes — tracked in KANBAN.
    HTTP_CODE=$(curl -sS -o /tmp/ingest-response.txt -w "%{http_code}" \
        -X POST \
        -H "Origin: https://askmytown.org" \
        --netrc-file "$CREDS_FILE" \
        https://askmytown.org/api/admin/ingest)
    echo "Ingest HTTP $HTTP_CODE"
    cat /tmp/ingest-response.txt
    echo
    if [ "$HTTP_CODE" != "200" ]; then
        echo "Ingest FAILED with status $HTTP_CODE."
        exit 1
    fi
else
    echo "WARNING: no credentials at $CREDS_FILE — skipping ingest."
fi

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily_update done ==="
