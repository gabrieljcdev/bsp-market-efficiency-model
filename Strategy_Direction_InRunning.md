# Strategy Direction — In-Running Betfair Trading Viability
## Stage 0: Pre-Registration of the Claim

**Date:** 2026-07-01
**Status:** STAGE 0 ONLY — pre-registration, awaiting confirmation of N / X / Y and the
pass/fail bar. **No Betfair historical data purchased. No backtest / fill-simulation
code written. No signal fitted.** Stage 1 (data purchase → liquidity feasibility →
edge test) is separately authorized ONLY after these numbers are confirmed.

---

### 0. Why pre-register (the discipline this enforces)
Every free-data test this project has run ended the same way: a fat-looking number
that turned out to be a **mechanical artifact**, not edge — the WAP-vs-close timing
offset, the favourite-longshot longshot tail, small-sample betting variance
(bigfield +30.38% ±14.5%). In-running adds a **second, deadlier artifact on top**:
paper fills at the *displayed* price for *unlimited* size. A backtest that assumes it
can get matched at the price on screen will manufacture an edge that does not exist
in a live market. So we fix the falsifiable claim, the null, the **fill model**, and
the pass/fail bar in writing, BEFORE seeing data or spending money — exactly as the
verdict/canary discipline was fixed before each pre-off probe.

### 1. The claim (one falsifiable sentence)
> At a realistic, latency- and liquidity-constrained fill model, a pre-registered
> in-running entry signal can get **≥ £X matched in > Y% of ≥ N qualifying
> opportunities**, AND the net-commission ROI on the **matched subset** beats the
> price-band-stratified structural in-running null by **≥ +1.0%** and is **> 0**,
> out of sample.

If either half fails on the holdout, the direction is abandoned.

### 2. PRIMARY GATE — LIQUIDITY FIRST (the cheapest kill)
The most likely and cheapest-to-test failure is that **achievable matched size at a
realistic fill is trivially small**. Prior belief (stated up front, to be falsified):
this probably fails here. So Stage 1 tests **liquidity first**; the edge test is only
run if liquidity passes. This front-loads the cheap kill and avoids paying for/writing
the expensive edge backtest on a strategy that can never be filled.

**Proposed parameters (for your confirmation):**

| symbol | meaning | proposed value | rationale |
|---|---|---|---|
| **N** | min qualifying opportunities in the study window | **2,000** | at a 50% fill rate the SE is ~1.1% (95% CI ±2.2%), so a true 45% vs 55% is cleanly distinguishable from the Y line. Liquidity is a market property, not a fitted quantity, so it is measured over the whole qualifying set (no discovery/holdout split needed for THIS gate). If qualifying opportunities are rarer than 2,000 in the window, widen the window rather than lower N. |
| **X** | target matched stake at the entry price, under the conservative fill model | **£100** | operational floor: below ~£100 matched the strategy is not worth running for a small pro, and commission + spread dominate. **TUNABLE to your bankroll** — raise it and the gate gets harder. |
| **Y** | fraction of qualifying opportunities in which ≥ £X must be matchable | **50%** | if you cannot get filled at your size in at least half the opportunities, realised edge (which only accrues on filled opportunities) is diluted below viability and execution is impractical. This is the ">50%" figure from the brief. |

**LIQUIDITY PASS/FAIL:** PASS-to-edge-stage iff **≥ £X matched (conservative fill) in
≥ Y% of ≥ N qualifying opportunities**. Otherwise **FAIL → abandon** (no edge work,
no further spend).

### 3. The conservative fill model (pre-registered — this is the crux)
The fill model is where the artifact lives, so it is pinned now, not chosen after
seeing data.
- **Data required (Stage 1 purchase):** Betfair historical in-running **price + traded
  volume at price** (the traded-ladder / market stream), NOT just BSP or LTP. Without
  volume-at-price you cannot reconstruct achievable matched size — the whole point.
- **Latency** `L = 1.0 s` between signal and matchable moment. You act on the ladder at
  `t + L`, never at the instant of the signal `t` (guards "the price I saw ≠ the price
  I got" during fast in-running moves).
- **Crossing the spread:** you take the available side. Matched £ =
  `min(£X, £ available at or through your price within slippage S = 1 tick)` at `t + L`.
- **Commission** = **2%** on net winnings. (CORRECTED 2026-07-01: an earlier draft
  carried 5% over from `clv.py`'s `DEFAULT_COMMISSION` by default — the canonical
  brief `prompts/InRunning_Stage0_PreRegistration.md` specifies 2%, which is right for
  an active in-running trader. Commission does NOT affect the liquidity gate — matched
  size is commission-independent — so this only bites at the edge gate.)
- An opportunity counts as **filled** only if ≥ £X is matched under this rule; a partial
  fill < £X counts as **not filled** (against Y).
- **Explicitly rejected fantasy:** matched at the displayed price for unlimited size.

### 4. SECONDARY GATE — EDGE (pre-registered now; tested ONLY if liquidity passes)
- **Metric:** net-2%-commission ROI per opportunity, computed on the **matched subset
  only** (opportunities where ≥ £X actually filled). Paper edge on unfillable
  opportunities does not count.
- **Null — NOT naive/uniform.** The **price-band-stratified structural in-running
  return**: each qualifying runner is benchmarked against the mean net outcome of all
  qualifying runners in its own **entry-price band** — the same discipline that closed
  the favourite-longshot hole in the pre-off pipeline. This strips the common,
  price-dependent in-running drift that everyone gets.
- **PASS (holdout):** matched-subset ROI **beats the stratified null by ≥ +1.0%**
  (the project's `EDGE_TOL`) **AND is > 0 absolute** (survives commission),
  **corroborated same-sign on discovery**.

### 5. POWER / CANARY (so a null result is informative, not just underpowered)
- **Hindsight-perfect-fill canary:** re-run the edge test replacing the realistic fill
  with the **best in-running price actually traded** in each opportunity. This MUST show
  a large edge — proving the rig can detect an edge *if one exists* (the in-running
  analog of the rpr canary used in the slice/target-C probes). **If even the
  hindsight-perfect fill shows no edge → INCONCLUSIVE** (data/signal underpowered), not
  a clean fail.

### 6. Discovery / holdout
Same time-split discipline as the rest of the project: discovery ≤ cutoff, holdout >
cutoff (default cutoff **2023-12-31** to match existing splits, or the data window's
midpoint — to be set at Stage 1). Verdict decided on **holdout**; discovery for
corroboration only. (Applies to the edge gate; the liquidity gate uses the full set.)

### 7. Kill criteria (ANY → abandon)
1. **Liquidity:** < Y% of qualifying opportunities can match £X (the expected primary kill).
2. **Edge:** matched-subset ROI ≤ 0 net commission, or ≤ null + tol, or not corroborated.
3. **Artifact:** an edge that exists ONLY under hindsight-perfect fill and vanishes under
   the realistic fill — that is a latency/liquidity artifact (the in-running analog of
   the WAP-vs-close timing artifact), not harvestable edge.

### 8. Qualifying opportunity — the ONE definition needing your input
The N/X/Y/bar framework above is signal-agnostic. It needs a concrete **entry signal**
to define a "qualifying opportunity." Proposed default instantiation, tied to what is
already built (leakage-clean `run_style_proxy`):
> a qualifying opportunity = a GB runner whose pre-race dominant run-style = **`led`**
> (a front-runner), entered when its in-running price **first trades ≤ P_trigger = 2.0**.

Rationale: front-runners have the most **mechanically predictable** in-running price
paths — they shorten sharply on an uncontested lead, then are layable as they tire.
This is a **placeholder to confirm or replace** with your intended signal; nothing else
in the pre-registration depends on it.

### 9. Explicit Stage-0 non-goals (what is NOT happening yet)
- No Betfair historical in-running data purchased.
- No backtest / fill-simulation code written.
- No signal fitting or parameter search.

### 10. What Stage 1 will need (for your review at authorization, not now)
- Betfair historical **in-running price + traded-volume-at-price** stream for GB racing
  over the split window (Advanced/Pro tier or a recorded stream). Scope/price to be
  quoted and approved at Stage 1 — **not purchased now**.
- Stage 1 order of work: (a) liquidity feasibility study (gate §2) → if PASS, (b) edge
  test (gate §4) with the canary (§5) and holdout verdict (§6).

---

**CONFIRMED 2026-07-01:** N = 2,000, X = £100, Y = 50%; edge bar ≥ +1.0% over the
stratified null AND > 0 net commission; fill model L = 1.0 s, S = 1 tick, **2%
commission** (corrected from 5%); liquidity-gate signal = front-runner
(`run_style_proxy = led`) entered when the in-running price first trades ≤ 2.0. Stage 1
is authorized for the **LIQUIDITY GATE ONLY** — report the liquidity result and wait
for confirmation before any further spend or the edge backtest.

(The suggested X in the canonical brief was £10; the confirmed £100 is a deliberately
harder bar — more likely to fail, which is the point of a cheap kill.)
