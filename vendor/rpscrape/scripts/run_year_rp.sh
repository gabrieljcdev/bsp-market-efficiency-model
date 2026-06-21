#!/usr/bin/env bash
# Resume-aware single-year RP scrape (Betfair read from pre-seeded cache).
# Usage: run_year_rp.sh <range> <filename>
#   range    e.g. 2023/01/01-2023/12/31   (passed to rpscrape -d)
#   filename e.g. 2023_01_01_2023_12_31   (used to name the log)
set -u
RANGE="$1"
NAME="$2"

cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
PY="$ROOT/.venv313/bin/python"
LOGDIR="$ROOT/output/pull_logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${NAME}_resume.log"

: > "$LOG"
echo "=== $NAME RP scrape start $(date -u +%FT%TZ) ===" >> "$LOG"
for attempt in 1 2 3 4 5 6; do
  echo "--- attempt $attempt start $(date -u +%FT%TZ) ---" >> "$LOG"
  timeout 12000 "$PY" rpscrape.py -d "$RANGE" -r gb >> "$LOG" 2>&1
  rc=$?
  echo "--- attempt $attempt exit=$rc $(date -u +%FT%TZ) ---" >> "$LOG"
  if [ "$rc" -eq 0 ]; then break; fi
  sleep 60
done
echo "=== $NAME RP scrape done $(date -u +%FT%TZ) ===" >> "$LOG"
