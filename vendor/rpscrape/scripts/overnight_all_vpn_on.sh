#!/usr/bin/env bash
# Unattended overnight run, VPN ON the whole time.
#   - 2023: Betfair cache exists -> scrape with betfair ON (form + BSP).
#   - 2024/2025/2026: no cache, Betfair geo-blocks the VPN -> scrape form-only
#     (betfair OFF) so it cannot crash; BSP is backfilled later VPN-OFF.
# Resume-aware + patient retries so a transient RP 406 doesn't lose the night.
set -u
cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
PY="$ROOT/.venv313/bin/python"
TOML="$ROOT/vendor/rpscrape/settings/user_settings.toml"
LOG="$ROOT/output/pull_logs/overnight.log"
mkdir -p "$ROOT/output/pull_logs"
: > "$LOG"

stamp() { date -u +%FT%TZ; }
set_betfair() { sed -i "s/^betfair_data = .*/betfair_data = $1 # Get Betfair data/" "$TOML"; }

# scrape_year <range> <name>  — resume-aware, up to 8 attempts, 5-min cooldown.
scrape_year() {
  local range="$1" name="$2" attempt rc
  echo ">>> $name START $(stamp)" >> "$LOG"
  for attempt in 1 2 3 4 5 6 7 8; do
    echo "--- $name attempt $attempt $(stamp) ---" >> "$LOG"
    timeout 18000 "$PY" rpscrape.py -d "$range" -r gb >> "$LOG" 2>&1
    rc=$?
    echo "--- $name attempt $attempt exit=$rc $(stamp) ---" >> "$LOG"
    [ "$rc" -eq 0 ] && break
    sleep 300
  done
  local f="$ROOT/vendor/rpscrape/data/region/gb/all/${name}.csv"
  echo ">>> $name DONE rows=$(wc -l < "$f" 2>/dev/null) $(stamp)" >> "$LOG"
}

echo "=== OVERNIGHT START $(stamp) ===" >> "$LOG"

# Phase 1 — 2023 with BSP (cache present)
set_betfair true
scrape_year 2023/01/01-2023/12/31 2023_01_01_2023_12_31

# Phase 2 — 2024-2026 form-only (BSP backfilled later, VPN-off)
set_betfair false
scrape_year 2024/01/01-2024/12/31 2024_01_01_2024_12_31
scrape_year 2025/01/01-2025/12/31 2025_01_01_2025_12_31
scrape_year 2026/01/01-2026/06/19 2026_01_01_2026_06_19

# restore default for next interactive session
set_betfair true

echo "=== OVERNIGHT DONE $(stamp) ===" >> "$LOG"
