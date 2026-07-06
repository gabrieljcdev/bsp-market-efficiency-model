# Pre-off Gate Report — Q2 / Q3 / Q6 (Betfair PRO, GB flat, 2015-05 → 2016-04)

**Governed by** `analysis/preregistration_inrunning.md` §12 Amendment 1 (committed `7aa0f28`,
before any pre-off statistic was computed). **Verdicts decided before money logic.**

## Headline

| Question | Gate 1 (fill feasibility) | Gate 2 (edge) | Net |
|---|---|---|---|
| **Q2** — T-10min ladder momentum → final-10-min direction | PASS (54.5% £100-fill) | **FAIL** | no edge |
| **Q3** — timestamped strike, 3rd-best-back @ T-10min (CLV vs BSP) | PASS (72.2% fill) | **FAIL** | value-destroying |
| **Q6** — pre-off passive quote (market-making) | PASS (71.1% fill rate) | **FAIL** | loses the spread |

**All three pass the cheap fill/liquidity kill but fail the edge gate.** Combined with Q1
(in-running liquidity, `82b9786`), the Betfair PRO **in-running *and* pre-off** trading
directions are now comprehensively closed — no market-orthogonal edge found in liquidity or
pre-off ladder microstructure on this 12-month GB-flat sample.

## Data & method

- Universe: GB flat WIN (self-classified, 99.67% accurate vs scraped `type`); **5,760
  markets, 56,847 runner-moments** (≫ the N=2,000 target), 57 markets dropped for no book
  near T-10min. International pull (GB≈35% of WIN markets) filtered out.
- Reconstruction: `backtest/pro_stream.py` (bz2-in-tar, hand-rolled `atb/atl/trd` deltas,
  bflw-validated exact). Pre-off snapshots at T-30/25/15/11/10 min + the last pre-off state;
  reconciled **BSP taken directly from the final `marketDefinition`** (`bsp` field, 91%
  populated). Fill model = §6 (£100 within 1 tick, 2% commission).
- Code: `backtest/gate_preoff.py` (extract + Gate 1), `backtest/gate_preoff_analysis.py`
  (Gate 2). **107/107 unit tests green**, incl. the band-null zeroing a common CLV offset.
- **Assistant-specified defaults** (per "execute end-to-end", flagged in the amendment):
  Q6 quote = two-sided touch-join, £100/side, posted T-30min, hedge at T-10min; S1≤6f /
  S2≤8 runners / S3=handicap.

## Gate 1 — fill feasibility (all PASS)

| | metric | value | bar | verdict |
|---|---|---|---|---|
| Q2 | £100 matchable within 1 tick at T-10min touch | 54.5% | >50% | PASS |
| Q3 | £100 matchable within 1 tick at 3rd-best-back | 72.2% | >50% | PASS |
| Q6 | fraction of posted passive quotes that ever fill | 71.1% | ≥10% | PASS |

Unlike the in-running touch (Q1: median £0 available), the pre-off book carries enough depth
for £100, and passive quotes fill often. So viability rests entirely on Gate 2.

## Gate 2 — edge (all FAIL)

### Q2 — direction model — FAIL
Logistic on {WAP/back-price momentum, log back/lay imbalance, volume acceleration} at
T-10min → P(shorten by the off). Bar: beat the band-stratified structural-drift baseline by
**≥ 2 ticks** AND net-2%-commission return > 0, on holdout AND both week-parities.

| split | n | edge vs baseline (ticks) | net return |
|---|---|---|---|
| holdout (2016 Jan-Apr) | 9,081 | **+0.078** | +4.4% |
| week-even | 25,416 | +0.002 | +6.4% |
| week-odd | 26,328 | +0.020 | +5.9% |

The model's directional tick-gain **matches the band's structural-drift baseline** (edge ≈ 0
everywhere, ≪ the +2-tick bar). The positive raw return is the well-known structural
FLB/steamer drift that a signal-free baseline already harvests — the "+2 ticks over baseline"
bar strips it exactly. **No incremental predictive skill.** FAIL.

### Q3 — timestamped-strike CLV — FAIL
Strike = 3rd-best-back @ T-10min; CLV = struck/BSP − 1.

| split | n | raw CLV mean |
|---|---|---|
| discovery | 42,821 | **−7.97%** |
| holdout | 9,148 | **−7.27%** |

Backing the 3rd rung deep in the book at T-10min gives **negative CLV** — you strike short of
where the market closes (BSP), then it drifts out. The frozen rule is value-destroying. FAIL.
*(Limitation: the price-band × course null is degenerate here — Q3 backs the whole
population, so "runner − cell-mean" ≈ 0 by construction; the verdict rests on the decisive
negative raw CLV, not the null. Brier corroboration deferred — win/loss not extracted.)*

### Q6 — passive-quote P&L — FAIL

| split | n fills | P&L vs zero (net 2%) | p |
|---|---|---|---|
| discovery | 48,600 | **−1.13%** | ~0 |
| holdout | 11,419 | **−1.10%** | ~0 |

Passive quotes lose ~1.1% per filled round-trip, highly significant. **Adverse-selection
diagnostic** (best-back drift after a filled back, ticks): T-30→T-25min −0.21, →T-15min
−0.51, →T-10min **−0.58** — filled quotes get picked off just before the price moves against
them, and the T-10min hedge crosses the spread and pays it. Classic negative
market-making-without-edge. FAIL. *(Same whole-population band-null degeneracy as Q3; verdict
rests on P&L-vs-zero.)*

## Slices S1-S3

Not computed — **no question survived Gate 2**, so there were no survivors to slice. (Had any
survived, S1 sprints / S2 small fields / S3 handicaps would be reported BH-corrected as one
family.)

## Conclusion

Pre-off ladder microstructure on this GB-flat 2015-16 PRO sample carries **no harvestable
edge** after realistic fills + 2% commission: direction prediction adds nothing over
structural drift (Q2), the timestamped strike destroys value vs BSP (Q3), and passive quoting
loses the spread to adverse selection (Q6). Together with the in-running liquidity FAIL (Q1),
the Betfair PRO trading direction is closed at the gate. Consistent with every prior free-data
family: raw numbers that look positive are structural (FLB/drift/timing) artifacts, not edge.
