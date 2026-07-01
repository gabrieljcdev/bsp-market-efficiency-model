# Handover — In-Running Betfair Trading, Stage 1 PENDING

**Date:** 2026-07-01
**State:** Stage 0 pre-registered + confirmed. Stage 1 LIQUIDITY GATE run as a free
first-pass (data in hand) → **NOT KILLED / INCONCLUSIVE**. Awaiting a user decision on
whether to buy the paid ladder data for a definitive verdict. **Edge gate NOT started**
(explicitly gated behind the liquidity result + a fresh authorization).

---

## Confirmed pre-registration (do NOT retune after seeing data)
- **Signal (liquidity gate):** front-runner (`run_style_proxy == 'led'`) entered when the
  in-running price first trades **≤ 2.0**.
- **N** = 2,000 min qualifying opportunities · **X** = £100 target matched stake ·
  **Y** = 50% (must match ≥ £X in > Y% of opportunities).
- **Fill model:** latency **L = 1.0 s**, cross the spread, matched = `min(£X, size
  available within 1-tick slippage)` at `t + L`; an opportunity counts as filled only if
  ≥ £X matched.
- **Commission = 2%** (corrected from an inadvertent 5% carry-over from `clv.py`; the
  canonical brief specifies 2%). NB commission does not affect the liquidity gate.
- **Edge bar (NOT yet tested):** on the matched subset, net-2%-commission ROI beats a
  **price-band-stratified structural in-running null** by ≥ +1.0% AND > 0 absolute,
  discovery/holdout-corroborated, with a **hindsight-perfect-fill canary** to prove power.

Full spec: `Strategy_Direction_InRunning.md`. Canonical brief:
`prompts/InRunning_Stage0_PreRegistration.md`.

## Stage 1 liquidity gate — free first-pass result (`models/inrunning_liquidity_screen.py`)
Uses the Betfair in-play aggregates already in `joined_gb_2018_2026_hist.csv`
(`ip_min`/`ip_max`/`ip_vol`, 99.8% populated).

- Qualifying opportunities (led & `ip_min` ≤ 2.0): **21,416** (≫ N_MIN 2,000).
- TOTAL in-play matched volume per runner: **median £48,723**, p10 £17,679, p25 £28,784.
- Fraction with `ip_vol` ≥ £100: **100.0%** (discovery 100%, holdout 100%).

**Why this is not a PASS:** `ip_vol` is the TOTAL matched in running (whole in-play
period, all prices, both sides), so `ip_vol ≥ £X` is an **upper bound** on the true
point-in-time matched size at ≤ 2.0 at `t + 1 s`. The screen can only DECISIVELY FAIL
(it didn't) — it cannot confirm the point-in-time fill. **Verdict: NOT KILLED /
INCONCLUSIVE at zero cost.** The cheap kill did not fire; front-runners trading ≤ 2.0
are heavily traded in running (£100 is ~0.2% of median in-play volume), but whether
£100 is available at your price at your instant is unanswered.

## Blocker / decision required
A **definitive** liquidity verdict needs **Betfair Historical Data PRO tier** (50 ms,
full ladder + volume) from historicdata.betfair.com — a **paid purchase that must be
made by the user** (Betfair account + payment + manual download; the assistant cannot
purchase autonomously). Data is not re-purchasable, so size the sample right first time.

**Acquisition spec when/if buying:**
- PRO tier, 50 ms, full ladder + traded volume; UK horse racing; mix of festival +
  midweek/lower-grade; a sample yielding **≥ 2,000 qualifying opportunities**
  (front-runners trading ≤ 2.0) spanning the discovery/holdout split.
- **Verify each market's actual `betDelay`** rather than assuming 1 s (some sources cite 2 s).

## Next steps (in order; each gated on the prior)
1. **[USER]** Decide: buy the PRO ladder sample, or accept the free screen's read and stop.
2. **[on data]** Run the point-in-time fill model against the pre-registered liquidity
   gate (≥ £X matched in > Y% at ≤ 2.0, `t + 1 s`). Report PASS/FAIL. **Then STOP.**
3. **[only if liquidity PASS + fresh authorization]** Run the edge gate (§4 of the
   pre-reg) with the stratified null + hindsight canary + holdout verdict. The edge-gate
   *signal* is to be revisited then (the ≤ 2.0 front-runner rule was fixed for liquidity
   only; the brief's momentum/reaction hypothesis is a candidate).

## Discipline carried from the rest of the project
- Do not retune N/X/Y/the rule after seeing data (the trainer_course_sr mirage lesson).
- The realistic fill model is the single biggest false-positive source — be conservative;
  count a fill only when price trades THROUGH your level, cap at available size.
- A fat number that exists only under an optimistic/hindsight fill is the in-running
  analog of the WAP-vs-close timing artifact → not harvestable.
- Leakage within a race: only use price/volume that existed at the simulated instant,
  never later ticks in the same race (the intra-race analog of "strictly-prior runs").
