# UI notes — racing_rulebuilder

Operational gotchas for the rule-builder tool and its bridge. Keep short; one fact per bullet.

## Data

- **The joined CSV is NOT globally date-sorted.** `data/joined/joined_gb_2018_2026.csv`
  has a date discontinuity around **row ~452717** (e.g. a `2023-05-11` row appears
  after later dates). Any code that depends on chronological order **must sort by
  `date` first** — never assume row order is time order.
  - This already bit two places, both handled by sorting first:
    - the staking/bankroll compound path (`_staking_curves` sorts bets by date),
    - **the pending Layer-2 history join** (runner view / scanner Tier 2): for each
      runner take only runs with `date < this race's date`, after sorting. A naive
      join on unsorted rows — or one that includes the current/future run — silently
      leaks the result. Same class of error as the post-race column gate.

## Leakage discipline (display vs selection)

- Selection-input columns are pre-race only. Post-race columns (`pos`, `bsp`, `wap`,
  `rpr`, `dec`, finishing data) may be shown **display-only** on historical rows,
  never as selection inputs, and are **empty on today's cards** (the race hasn't run).
- Browse surfaces (race view, runner view, flag auto-scan) never filter as a second
  rule engine — strategy filtering lives only in Build / the bridge selection gate.

## Bridge

- `python run_strategy.py --serve` → `127.0.0.1:8765`. Routes: `/run`, `/scan`,
  `/races`, `/runners`. CORS `*` so the `file://`/static-served UI can reach it.
- struck = `wap`, benchmark = `bsp`, commission 5%.
