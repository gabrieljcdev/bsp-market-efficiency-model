#!/usr/bin/env bash
# Phase A (run VPN-OFF, home/UK IP): prefetch Betfair SP caches for all
# remaining years in one shot. Each is skipped if its cache already exists,
# so this is safe to re-run. Output caches feed the VPN-ON RP scrape.
set -u
cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
PY="$ROOT/.venv313/bin/python"
LOG="$ROOT/output/pull_logs/betfair_prefetch.log"
mkdir -p "$ROOT/output/pull_logs"
: > "$LOG"

# start  end  filename
YEARS="
2024-01-01 2024-12-31 2024_01_01_2024_12_31
2025-01-01 2025-12-31 2025_01_01_2025_12_31
2026-01-01 2026-06-19 2026_01_01_2026_06_19
"

echo "=== betfair prefetch start $(date -u +%FT%TZ) ===" >> "$LOG"
echo "$YEARS" | while read -r start end name; do
  [ -z "${name:-}" ] && continue
  echo "--- $name start $(date -u +%FT%TZ) ---" >> "$LOG"
  "$PY" prefetch_betfair.py "$start" "$end" "$name" >> "$LOG" 2>&1
  echo "--- $name exit=$? $(date -u +%FT%TZ) ---" >> "$LOG"
done
echo "=== betfair prefetch done $(date -u +%FT%TZ) ===" >> "$LOG"
