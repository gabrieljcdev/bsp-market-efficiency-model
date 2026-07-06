# Q7 — Non-runner repricing latency: Gate 1 + Gate 2 report

**Governs / pinned by:** `analysis/preregistration_inrunning.md` §12 **Amendment 2**
(committed `6759710`, *before* first Q7 data contact). Universe = GB-flat WIN, 2015-05
→ 2016-04 (12 PRO tars). Commission 2%. Nothing here was retuned after data contact.

**Verdict: PRICED.** The non-runner RF-repricing latency is real and *detectable* — the
suspend-and-cancel mechanic is leakier than the "deletes the opportunity by design"
prior — but the residual stale quote is **not harvestable**: the trade does not beat the
ambient spread/churn base rate, loses on the well-powered discovery partition, and flips
sign violently across the pre-registered splits.

---

## Scope (Amendment 2)
Of the announcement family (NR / going change / jockey change), **only NR withdrawals
are stream-observable** (`runners[].status → REMOVED` + `adjustmentFactor`). Going and
jockey changes emit no `marketDefinition` event → **untestable on this data, excluded.**

## Event definition (frozen)
`ACTIVE → REMOVED`, GB-flat WIN, **pre-off**, `adjustmentFactor ≥ 2.5%`. `t` = publishTime
of the REMOVED transition. Pre-state at t−1s; post at 1s snapshots t+1s…t+300s. Fair
benchmark `P_fair,i = P_pre,i·(1−A)`, `A = Σ adjustmentFactor/100` (probability-renorm;
Betfair matched-bet `1+(P−1)(1−A)` reported as cross-check). Opportunity = ≥2-tick-stale
available size at t+k (k=1…30s), either side; entry @1s latency, £50/runner; exit @touch
t+300s; net 2%.

---

## GATE 1 — fillability + mandatory diagnostics  → **PASS (marginal)**
`models/gate_q7_gate1_results.json` · 12 tars · 1,140 s wall.

| metric | value |
|---|---|
| qualifying NR events | **4,079** across 309 racedays (**12.8 / raceday**) |
| adjustmentFactor % | min 2.5, median **7.7**, max 100.2 |
| **fillability (≥£50 stale)** | **12.82%** (523/4,079) → **PASS** (bar 10%) |
| fillability, matched-bet benchmark | **9.86%** → would FAIL (benchmark-sensitive) |
| best-opportunity size | median **£2**, p90 **£71** |

**Mandatory diagnostics — the mechanic, characterised:**
- **Suspend fraction: 15.2%** captured SUSPENDED in the 1s grid; of those, suspension
  duration median **1 s** (p90 85 s, 50 censored at 300 s). The median-1s figure means
  most suspensions are **sub-second and missed by 1s sampling** — a measurement floor, so
  15.2% is a *lower bound* on true suspension incidence.
- **Book wipe:** depth at t+1s is a median **27%** of the t−1s level (p10 15%); only
  **4.2%** of events are near-fully wiped (≤10%). So unmatched cancellation thins the book
  hard but rarely empties it.
- **Repopulation to 80% of pre-depth:** only **47.6%** of events recover within 300 s
  (median 14 s, p90 42 s) — over half stay materially thin for the whole 5-min window.

**Read:** Betfair *does* suspend + cancel unmatched on a removal, but the mechanic is
leakier than the pre-registered "deletes by design" expectation — a ≥£50 stale quote
survives in ~1 event in 8. Whether that is *money* is Gate 2 (the fillability bar is
absolute; the 12.8% is only meaningful vs the ambient base rate the null measures).

---

## GATE 2 — edge vs the band × time-to-off-matched non-NR null  → **PRICED**
`models/gate_q7_gate2_results.json` · 1,095 s wall · net-2% P&L per £ matched.
Null = the identical "fade a ≥2-tick-stale quote, hold 300 s" trade at random non-NR
control moments in the **same** markets (≥120 s from any removal, A=0), band × tto matched.

| split | n NR trades | NR ROI/£ | control ROI/£ | **matched edge/£** |
|---|---:|---:|---:|---:|
| overall | 759 | +0.0110 | +0.0042 | **+0.0089** |
| **discovery** (2015) | 653 | **−0.0274** | +0.0072 | **−0.0315** |
| **holdout** (2016) | 106 | +0.2482 | −0.0126 | **+0.2590** |
| parity even | 369 | +0.0241 | −0.0043 | **+0.0287** |
| parity odd | 390 | −0.0013 | +0.0115 | **−0.0094** |

**Why PRICED (pre-registered rule: edge must be > 0 AND same-sign on holdout AND
discovery AND both week parities):**
- **Discovery (653 trades — the well-powered bulk): matched edge −3.1%**, and the raw NR
  return is itself **negative** (−2.7%). On the sample with power, the removal trade *loses*
  and is *worse* than the same trade at random moments.
- **Holdout's +25.9%** is on **106 trades**, its own control is −1.3% (season-confounded,
  §7), and it **flips sign vs discovery and vs parity-odd**. This is the textbook
  small-sample longshot-tail noise the project has repeatedly killed (Target C +3.14%→½
  OOS; big-field +30% SE±14.5%), not a stable edge.
- Two of four splits are **negative**; the rule fails outright.

**Mechanism of the kill:** the RF shift is instantaneous and known, but by the time
1s-latency retail can act, (i) the market has often suspended and cancelled the very
unmatched quote you would hit, (ii) the book has thinned to ~27% and stays thin, and
(iii) the residual stale quotes that *are* fillable are longshot-tail, tiny (median £2),
and — on the powered sample — return *below* the ambient spread/churn you'd earn fading
any 2-tick-stale quote. Net of 2% and the 300 s round-trip, there is no removal edge.

---

## Limitations (pre-registered honesty)
- **1s snapshot grid** floors the suspension-incidence and latency measurements (median
  suspension is 1 s ⇒ sub-second events under-counted). Direction of the Gate-2 verdict
  is unaffected — a faster grid would show *more* suspension, i.e. *less* opportunity.
- **Extreme AF** (a handful with AF ≳ 50–100%) makes `P_fair = P_pre·(1−A)` degenerate
  (→ ~0/negative); these are a tiny minority and do not move the medians or the verdict.
- **2015-16 regime, ~10 y stale** (§8): modern books/bots would reprice *faster*, further
  shrinking any latency window — the conclusion is conservative for a 2026 deployment.
- **Season confound** in the chronological split (§7) is visible in the control ROI itself
  (discovery +0.7% vs holdout −1.3%); the odd/even-week parity leg is the mitigation and
  it too is negative (−0.9%), corroborating PRICED.

## Cross-cutting
Q7 joins Q1 (in-running liquidity, FAIL) and Q2/Q3/Q6 (pre-off momentum/CLV/quote, FAIL)
— the event-driven latency axis is priced just like the standing-signal axes. Same
land-pattern as every prior family: a real, detectable structural feature (here the
RF-repricing lag) that the market/mechanic has already closed to a 1s-latency taker.
