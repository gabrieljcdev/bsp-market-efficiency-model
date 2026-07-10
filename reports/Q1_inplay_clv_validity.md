# Q1 — Does CLV transfer to in-play?

# VERDICT: NOT SAFE

A closing-line-value metric computed against a *pseudo-close* reconstructed from
in-running prices does **not** rank in-play trading rules the way absolute realised
return does. It fails all three pre-registered NOT-SAFE triggers independently, on a
large, well-powered sample. `backtest/clv.py` ports to football as **plumbing only**.

- **Pre-registration:** `prompts/Q1_INP.MD`, committed `694ae7b` (2026-07-09), *before* any
  code was run or any of these numbers were seen. Decision rule in §5 of that file was not
  renegotiated after results.
- **Data:** real Betfair PRO historical stream tars in `data/historical/betfair_pro/`
  (GB flat WIN, ~2015–16), reconstructed to a 1-second in-running order book + last-traded
  series by `backtest.pro_stream`. Discovery-only era (pre-2018); **the 2025–26 holdout was
  not touched.** No data was purchased.
- **Coverage:** 12 tars → 5,760 GB-flat markets scored → **116,189 opportunities**. Commission
  **hardcoded 0.02** (`DEFAULT_COMMISSION`=0.05 was never read, per pre-reg §1). Wall clock 34 min.
- **Harness:** `backtest/q1_clv_validity.py`; unit tests `backtest/test_q1_clv_validity.py` (11
  tests, all passing — pin R5→0 on zero-edge data, known-edge detection, zero-match join guard,
  Kendall τ maths). Results JSON `models/q1_clv_validity_results.json`.

---

## 1. Canary first — is the test powered? YES.

Pre-reg §4 gates everything on C1: a hindsight-perfect fill (best price in the entry window,
zero latency/slippage) must show a **large** edge on at least one of R1–R4, else the result is
INCONCLUSIVE (underpowered). It does, on three:

| Rule | C1 hindsight ROI |
|------|-----------------:|
| R1 (short-price back) | **+53.3%** |
| R4 (front-runner back) | **+48.3%** |
| R3 (drifter back) | **+33.2%** |

The data can separate large effects. Metric disagreement below is therefore a real property of
the metrics, not an artefact of a sample too weak to rank anything.

---

## 2. Results table (rows R1–R5 × G1, G2, C1, P1, P2, P3, n)

Ground truth: **G1** = absolute realised ROI (net 2% comm) on the modelled fill (1.0s latency,
cross-spread, 1-tick slip). **G2** = G1 minus the price-band-stratified zero-skill band-common
return (14 bands, <50 obs → global). **C1** = hindsight canary (above).
Metrics under test: **P1/P2/P3** = `struck / pseudo_close − 1`, pseudo-close = final in-running
LTP / LTP at entry+30s / BSP respectively. CLV shown as %.

| Rule | side | n (entries / filled) | **G1 ROI** | **G2 vs null** | **C1** | **P1 CLV** | **P2 CLV** | **P3 CLV** |
|------|:----:|---------------------:|-----------:|---------------:|-------:|-----------:|-----------:|-----------:|
| R1 back ≤2.0        | back | 10,898 / 5,455 | **+2.42%**  | +2.17%  | +53.3% | +40.4%  | +3.10%  | −41.8% |
| R2 lay ≤1.5         | lay  |  8,215 / 2,820 | **−8.37%**  | −0.00%  | +6.64% | +945%   | **+6606%** | +584% |
| R3 drifter ≥2×BSP   | back | 47,713 / 10,979 | **−38.40%** | +7.22%  | +33.2% | +684%   | −21.3%  | +338% |
| R4 led + ≤2.0       | back |  1,612 / 791   | **+5.53%**  | +5.30%  | +48.3% | +16.1%  | +7.22%  | −46.8% |
| R5 random control   | back | 47,751 / 20,924 | **−41.72%** | −4.55%  | −14.2% | +422%   | −16.4%  | +441% |

Every G2 sits next to its G1 (pre-reg §6). Note R3's positive G2 (+7.22%) against a deeply
negative G1 (−38.4%) — a differential that would flatter a drifter-back rule that in fact loses
38% absolute. This is exactly the "differential without its absolute" trap §6 warns of; it is
reported here only paired.

---

## 3. Proxy-spread table — `max(P) − min(P)` over P1/P2/P3, same rule

The heart of the test (pre-reg §5.4): how far the metric moves when only the *close proxy*
changes and the underlying bets do not. Threshold for NOT SAFE is **>10 percentage points on
any rule**.

| Rule | spread P1/P2/P3 | spread P1/P2 | > 10pp? |
|------|----------------:|-------------:|:-------:|
| R1 | 82.2 pp   | 37.3 pp  | ✗ fails |
| R2 | 6,022 pp  | 5,661 pp | ✗ fails |
| R3 | 706 pp    | 706 pp   | ✗ fails |
| R4 | 62.9 pp   | 8.9 pp   | ✗ fails |
| R5 | 457 pp    | 438 pp   | ✗ fails |

**Every rule** blows the 10pp gate — most by two to three orders of magnitude. For context, the
project's prior struck-side pathology (`HANDOVER` §9.2) swung 27.5pp. The close side here swings
up to 6,022pp on the same bets.

---

## 4. Kendall τ matrix — proxy ranking of R1–R5 vs ground truth

Requirement for PROXY-ROBUST: τ ≥ +0.8 against G1 for **both** P1 and P2.

| pseudo-close | τ vs G1 (abs ROI) | τ vs G2 (null diff) |
|--------------|------------------:|--------------------:|
| P1 (final LTP) | **−0.4** | −0.2 |
| P2 (LTP t+30s) | **+0.4** | −0.2 |
| P3 (BSP)       | **−0.6** | −0.4 |

No proxy reaches +0.8. P1 and P3 are *anti-correlated* with true ROI ranking; P2 is weakly
positive but nowhere near the bar. The three proxies do not even agree with **each other** on
the ordering.

---

## 5. Why it fails — the mechanism (stated after the verdict, not in place of it)

In-play there is no starting price: the market **resolves**, it does not reconcile. The final
in-running price is therefore *degenerate* — it converges to ≈1.01 for the winner and drifts
toward ∞ for every loser. So P1's `struck/close − 1`:

- for a winning back bet at odds `s`, → `s/1.01 − 1` ≈ `s − 1` — an **unbounded** positive
  "CLV" that grows with the odds backed, and rewards backing a longshot that happens to win;
- for a losing back bet, → `s/∞ − 1` ≈ −1.

P1 CLV thus re-encodes *did the horse win* (weighted by odds), not *did you beat the market*.
This is why the **random control R5 is awarded +422% CLV under P1 and +441% under P3** — a rule
with no edge scores hugely positive purely because its longshot winners' final prices collapse.
A metric that pins a medal on the random control is broken, and pre-reg §3 says that finding is
reportable on its own. It is: **P1 and P3 both award R5 a positive verdict.**

The lay side is worse still: R2's `close/struck − 1` divides a drifting loser's huge in-running
price by a ~1.5 lay strike, manufacturing +6,606% mean "CLV" on a rule whose realised ROI is
−8.4%. P3 (BSP) misbehaves throughout as designed — it is the pre-off close, not an in-play one.

---

## 6. NOT-SAFE triggers — all three fire independently (pre-reg §5)

1. **Sign disagreement with G1 on R1–R4:** P3/R1, P1/R2, P2/R2, P3/R2, P1/R3, P3/R3, P3/R4.
2. **Proxy spread > 10pp:** all five rules (§3).
3. **R5 awarded positive verdict:** under P1 (+422%) and P3 (+441%).

Any one is sufficient. PROXY-ROBUST would have required sign-agreement + τ≥0.8 + spread≤3pp on
P1/P2 + R5≈0 + P3-misbehaves *simultaneously*; it fails every clause except the last.

---

## 7. Caveats / anti-fooling (pre-reg §6)

- **Sample sizes** all healthy; no R1–R4 rule is under the 200-entry flag (smallest is R4 at
  1,612 entries / 791 filled). The verdict is not driven by a thin cell.
- **Zero-match guard armed:** `assert_coverage` requires non-zero flat-markets and opportunities;
  5,760 and 116,189 respectively. Run-style join (for R4's `led`) matched live — R4 fired 1,612
  times, so the form join is not silently empty.
- **Leakage:** entries are detected from the in-running LTP step-series keyed by publish-time;
  fills are struck at `signal_pt + max(1s, betDelay)`; the P2 proxy at `entry+30s` is truncated
  in <0.1% of fills (`p2_truncated_frac` ≤ 0.0009). No entry field post-dates its entry instant.
- **Attacked before reporting:** the enormous CLV magnitudes were re-derived by hand (§5) rather
  than taken at face value — they are the metric's genuine behaviour, not an overflow bug; the
  1-tar smoke run reproduced the same structure (R2 P2 ≈ +6,700%) independently.
- **Commission** used = **0.02** (hardcoded); `DEFAULT_COMMISSION` (0.05) deliberately not read.

---

## 8. What this changes downstream (pre-reg §7.6)

For the football pre-registration, when it is written (not in this task):

> **`backtest/clv.py` ports as plumbing only, not as a scoring criterion.** In-play has no
> Starting Price, so there is no valid closing line to compute value against; a pseudo-close
> reconstructed from in-running prices is degenerate (it re-encodes the result) and unstable
> (it swings thousands of basis points on the choice of proxy while the bets are fixed). The
> Step-1 edge gate must therefore be written against the **price-band-stratified in-running
> null (G2)** — absolute return > 0 after 2% commission, beating the band-common return, and
> holdout-corroborated — exactly as `run_strategy.py`'s stratified null already does for the
> pre-off market. CLV may be carried only as a **secondary diagnostic on markets that genuinely
> reconcile to a BSP-style close, never as the in-play edge criterion, and never as sole
> evidence.** This must land in the football handover's "files that port unchanged" section
> (the analogue of `HANDOVER` §2.1) and its Step-1 gate definition *before* any tick data is
> purchased.

The cost of the opposite error — trusting in-play CLV — would have been a bought month of tick
data and a model scored against a number that means "it won", not "it had edge". A cheap honest
null was the product; this is it.
