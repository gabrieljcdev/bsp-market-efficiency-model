# Pre-Registration — In-Running / Trading Gate Program (Q1–Q4)

**Governs:** all gate/analysis work on `data/historical/betfair_pro/` (Betfair PRO
full-ladder + traded-volume stream, GB horse racing, May-2015 → Apr-2016).
**Status:** DRAFT — committed *before first data contact*, **awaiting user sign-off**.
No parser/analysis code has been run against the PRO market content for gate work.
**Date committed:** 2026-07-05.

---

## 0. The immutability rule (the whole point of this document)

This document fixes the falsifiable claims, nulls, fill model, splits, and pass/fail
bars **before** looking at a single tick of the PRO market stream — the exact
discipline that made the pre-race work trustworthy and that the free-data catalogue
(Test 1–8) and Test 4 enforced.

- **Nothing here may be altered after first data contact** except by a **dated
  amendment** in §12 stating *what changed and why*. Deciding a bar after seeing
  results is how the `trainer_course_sr` mirage happened; this rule exists to make
  that impossible.
- **"First data contact" is defined precisely** as: the first time any script
  decompresses and parses the *content* (JSON stream) of a `data/historical/betfair_pro/`
  market file **for Q1–Q4 gate work**. It **explicitly excludes** the ≤10-market
  ingest-validation sample already taken on 2026-07-04/05 (recorded in `PROJECT_NOTES.md`),
  which only confirmed PRO fields (`atb`/`atl`/`trd`, sub-second `pt`, `eventTypeId`,
  `countryCode`) and fitted nothing. Path-only `tar -tf` listings (the ingest inventory)
  are likewise not data contact.
- Edits **before** sign-off + first parse are free (still pre-registration); they do
  **not** require a §12 amendment. The lock engages at first gate parse.

---

## 1. Provenance & inherited discipline (non-negotiable, carried verbatim)

Same rules as the eight-test free-data program and Test 4. Money logic is written
**after** the verdict rig, never before.

- **Pre-register the bar before the data** — claim, null, fill model, pass/fail fixed
  in writing first (this file).
- **Price-band-stratified structural nulls**, not naive/uniform ones — each qualifying
  runner is benchmarked against the mean outcome of all qualifying runners *in its own
  entry-price band*. This is what closed the favourite-longshot hole pre-off and named
  the Test 4 lay artifact (the +32% "edge" that was pure BSP-band composition).
- **Per-course stratification** on top of price bands (§9) — course geometry drives
  in-running price paths; an unstratified null invites a course-composition artifact
  (the in-running analog of the Test 4 BSP-band-composition artifact).
- **Brier-corroboration gate** where a probability/forecast claim is made — a CLV/
  drift edge that carries no forecasting skill (fails to beat BSP on Brier) is flagged
  CLV-relative-only, exactly as Test 4 V2 was.
- **Discovery / holdout split** (§7), verdict on holdout, discovery for same-sign
  corroboration only.
- **Hindsight-perfect-fill / rpr-style power canary** (§ per-question) — so a null
  result is *informative*, not merely underpowered.
- **Conservative fill model is the crux** (§6) — paper fills at the displayed price for
  unlimited size are the deadliest in-running artifact. Pinned now, never chosen after.
- **Intra-race leakage discipline** — a rule may only use price/volume that existed at
  the *simulated instant*, never a later tick in the same race (the within-race analog
  of "strictly-prior runs only").
- **Report the kill.** If a question fails as specified, that IS the result. No retune-
  to-pass; no post-hoc subpopulation narrowing.

**Reference docs (canonical, read alongside this file):**
- `Strategy_Direction_InRunning.md` — full Stage-0 spec of the liquidity + edge gates (source of Q1/Q2).
- `prompts/InRunning_Stage0_PreRegistration.md` — canonical Stage-0/1 brief (2% commission, fill model).
- `Handover_InRunning_Stage1_Pending.md` — free-screen liquidity first-pass (NOT KILLED / INCONCLUSIVE).
- `Milestone_Eight_Tests_Summary.md` — summary of the eight free-data tests. **⚠ NOT YET IN REPO** (to be compiled from the PROJECT_NOTES Test 1–8 entries; see §13). Until it exists, the canonical record is the dated PROJECT_NOTES entries + `prompts/test_4_prompt.md`.
- `PROJECT_NOTES.md` — the 2026-07-03 **Test 4** lay-side note (the named-artifact exemplar) and the 2026-07-04/05 PRO ingest note.

---

## 2. The data (fixed universe of this study — facts from ingest, no content parsed)

From the path-only ingest inventory (`PROJECT_NOTES.md`, 2026-07-04/05):
- **12 tars, 45.71 GiB, 153,613 members**, PRO tier (`atb`/`atl`/`trd` ladders +
  sub-second `publishTime` confirmed on the validation sample).
- **One continuous block: 2015-05-01 → 2016-04-30 = 365 racedays** (only 2015-12-25
  absent = no GB racing → not a gap). 7 stray 2016–18 days are out-of-window noise, **excluded**.
- `eventTypeId == 7` (horse racing) = 100% of the validation sample; countryCode
  predominantly **GB**, some **IE**.

This 12-month window is the **entire** evidentiary base. Every Q1–Q4 verdict is a
verdict *about GB flat in-running/pre-off microstructure in 2015-16* and is caveated
accordingly (§8).

---

## 3. Universe — GB FLAT only (turf + AW); jumps EXCLUDED ex ante

- **Included:** GB (`countryCode == "GB"`), `eventTypeId == 7`, **flat** races only
  (turf + all-weather). Selection is by `marketDefinition` (`countryCode`, `marketType`
  = `WIN`, and race-type/name flat classification), cross-checked against the project's
  existing course/going reference where a market maps to a known GB flat course.
- **IE excluded** by default (window is a GB study; IE markets in the pull are dropped,
  not analysed). If an IE inclusion is ever wanted it is a §12 amendment.
- **Jumps EXCLUDED ex ante — pre-registered reason:** a faller/unseat/pull-up on a
  jumps runner imposes a **3–10% per-runner faller cost** that makes an **unhedged
  back-to-lay in-running tail risk unacceptable** (a leader you have laid can be
  brought down or fall while you hold liability). Flat has a near-zero non-completion
  rate, so the in-running lay-the-tiring-leader family has **bounded** tail risk there.
  **Jumps are a separate future program**, not a subpopulation of this one — they are
  not revisited by any Q1–Q4 amendment.
- **Non-completion handling (flat, rare):** a runner that falls / unseats / is pulled
  up / refuses is scored at its **actual Betfair settlement** (loser / void per market
  rules), never silently voided or dropped — dropping them would understate exactly the
  tail this universe is chosen to bound. The realised faller rate in the flat sample is
  reported as a robustness figure.

---

## 4. Q1 — LIQUIDITY FEASIBILITY  *(PRIMARY gate; the cheapest kill)*  — CONFIRMED

Transcribed from the confirmed Stage-0 pre-registration (`Strategy_Direction_InRunning.md`
§2–3, confirmed 2026-07-01). Prior belief, stated to be falsified: **this probably
fails here.** Q1 runs first; Q2 is only run if Q1 passes.

- **Claim:** a pre-registered in-running entry signal can get **≥ £X matched in > Y% of
  ≥ N qualifying opportunities** under a realistic, latency- and liquidity-constrained
  fill model.
- **Parameters (confirmed, do NOT retune):** **N = 2,000** qualifying opportunities ·
  **X = £100** target matched stake · **Y = 50%**.
- **Qualifying opportunity (confirmed placeholder signal):** a GB flat runner whose
  pre-race dominant run-style proxy = **`led`** (front-runner), entered when its
  in-running price **first trades ≤ P_trigger = 2.0**. (Signal-agnostic framework; this
  instantiation is fixed for Q1. The edge-gate signal may be revisited at Q2 — §5.)
- **Fill model (the crux, §6).** An opportunity counts as **filled** iff ≥ £X is matched
  under §6; a partial < £X is **not filled** (counts against Y).
- **Metric is liquidity, a market property** → measured over the **whole** qualifying
  set; **no discovery/holdout split for Q1** (liquidity is not fitted). If qualifying
  opportunities are rarer than N in the window, **widen nothing / lower nothing** —
  report the shortfall; the 365-day GB flat window is the fixed base.
- **PASS → run Q2** iff ≥ £X matched in ≥ Y% of ≥ N qualifying opportunities.
  **Otherwise FAIL → abandon the in-running direction** (no Q2, no further work).
- Note: the free-data first-pass (`models/inrunning_liquidity_screen.py`) was **NOT
  KILLED / INCONCLUSIVE** because `ip_vol` is a total-in-play **upper bound**; Q1 on the
  PRO ladder is the point-in-time test that turns that into a definitive PASS/FAIL.

---

## 5. Q2 — IN-RUNNING EDGE  *(SECONDARY gate; only if Q1 passes + fresh authorization)*  — CONFIRMED

Transcribed from `Strategy_Direction_InRunning.md` §4–5.

- **Claim:** on the **matched subset** (opportunities where ≥ £X actually filled), the
  net-2%-commission ROI beats the price-band-stratified structural in-running null by
  **≥ +1.0%** (`EDGE_TOL`) **AND is > 0** absolute, **corroborated same-sign on discovery**.
- **Metric:** net-of-2%-commission ROI per matched opportunity. Paper edge on unfillable
  opportunities does **not** count.
- **Null:** **price-band × course-stratified** structural in-running return (§9) — each
  qualifying runner benchmarked against the mean net outcome of all qualifying runners in
  its own entry-price band *and* course stratum. Strips the price-dependent (and course-
  dependent) in-running drift everyone gets.
- **Commission = 2%** on net winnings (canonical; the 5% in `clv.py` is a pre-off carry-
  over and does not apply here).
- **Power canary (mandatory):** re-run Q2 with the realistic fill replaced by the **best
  in-running price actually traded** in each opportunity. This MUST show a large edge
  (proves the rig can detect edge if one exists — the in-running analog of the rpr canary).
  **If even the hindsight-perfect fill shows no edge → INCONCLUSIVE**, not a clean fail.
- **Verdict on holdout** (§7); discovery for corroboration only.
- **Kill (any):** matched-subset ROI ≤ 0 net commission; or ≤ null + tol; or not
  same-sign corroborated; or **edge exists ONLY under hindsight-perfect fill and vanishes
  under the realistic fill** (a latency/liquidity artifact — the in-running analog of the
  WAP-vs-close timing artifact, not harvestable).

---

## 6. The conservative fill model (pinned now — shared by Q1/Q2 and any in-running question)

- **Data used:** in-running **price + traded-volume-at-price** (the `atb`/`atl`/`trd`
  ladders in the stream), never BSP/LTP alone.
- **Latency `L = 1.0 s`** between signal and matchable moment — act on the ladder at
  `t + L`, never at the signal instant `t`. **`betDelay` is VERIFIED per market** from
  `marketDefinition.betDelay` rather than assumed (some sources cite 2 s; if a market's
  `betDelay` ≠ 1 s, its own value is used and the mix is reported).
- **Cross the spread:** take the available side. Matched £ =
  `min(£X, £ available at or through your price within slippage S = 1 tick)` at `t + L`.
- A fill counts **only when price genuinely trades THROUGH your level** in the replayed
  book; cap at actually-available matched size; never assume infinite size at the
  displayed price. **When unsure, err MORE conservative** — optimism here manufactures
  false positives.

---

## 7. Discovery / holdout split (adapted to the 12-month PRO window)

The confirmed Stage-0 cutoff was 2023-12-31 "or the data window's midpoint — to be set
at Stage 1." The PRO window is 2015-05 → 2016-04, so the 2023 cutoff is inapplicable and
the **window split** governs:

- **Discovery = 2015-05-01 … 2015-12-31** (8 months, 244 racedays).
- **Holdout   = 2016-01-01 … 2016-04-30** (4 months, 121 racedays).
- **Verdict decided on holdout; discovery for same-sign corroboration only** (applies to
  Q2 and any fitted question; Q1 liquidity uses the full set, §4).
- **Pre-registered caveat:** a chronological split confounds *season* with *split*
  (discovery skews summer/autumn turf; holdout skews winter AW). This is accepted to
  preserve the no-look-ahead discipline; **per-course and per-going stratification (§9)
  is the mitigation**, and any PASS must survive within-stratum, not just in aggregate.
  *(Alternative offered for sign-off: odd/even-week interleave to balance season at the
  cost of adjacent-race proximity. Chronological is the default unless you choose otherwise.)*

---

## 8. Era weighting / external validity (2015-16 data → 2026 live market)

- The window is a **single 2015-16 regime**, so there is no *intra-window* era weighting
  to apply — all 365 racedays weighted equally. A within-window drift check (a rule/market
  change mid-sample) is run as robustness only.
- **The load-bearing caveat:** 2015-16 in-running microstructure is **~10 years stale**
  relative to a 2026 live deployment — `betDelay`, bot/algo prevalence, queue dynamics,
  commission tiers, and participant mix have all evolved. **Any Q1/Q2 PASS is PROVISIONAL**
  and does not authorise live capital on its own: it must be **re-confirmed on a small,
  current-era mini-sample** (a fresh recorded/purchased stream) before any live prototype.
  This is pre-registered so a 2015-16 pass cannot be quietly treated as a 2026 pass.

---

## 9. Per-course (and per-going) stratification

- The project already holds a **65-course static geometry table** (uphill finish, draw
  bias, straight/turning — `data/reference`), verified per-course for 11 courses.
- The structural in-running null (§5) is stratified by **price-band × course**; where a
  course cell is too thin (< the project's ~min-cell rule), courses are pooled by
  **geometry class** (e.g. uphill-finish / turning / straight-track) rather than left
  unstratified. Going (`marketDefinition` / reference) is a secondary stratum where
  populated.
- **Why:** in-running price paths are course-shaped (a front-runner on an uphill finish
  tires differently than on a flat straight). An unstratified null lets **course
  composition** masquerade as edge — the direct analog of the BSP-band-composition
  artifact Test 4 exposed. A PASS must hold **within** strata, not only pooled.

---

## 10. Q3 & Q4 — ⚠ PROPOSED, PENDING YOUR SIGN-OFF (prompt truncated here)

> **Transparency note:** the source prompt was cut off at the `## Q1–Q4` section
> (mid-word, "separate fu…"). Q1 and Q2 above are transcribed from your **confirmed**
> Stage-0 pre-registration and are safe. **Q3 and Q4 below are my proposals** — grounded
> in the PRO data's unique capabilities and the project's stated "next shots"
> (timestamped strike for true CLV; in-running) — **for you to confirm, edit, or
> replace.** They are pre-registration placeholders; the immutability lock (§0) does not
> engage until sign-off + first parse, so replacing them now costs nothing.

### Q3 (PROPOSED) — Pre-off ladder microstructure: true timestamped-strike CLV
The free work could only use WAP and BSP snapshots; every "edge" collapsed to the
**WAP-vs-close timing artifact**. The PRO ladder carries the *full pre-off traded ladder
second-by-second*, enabling a genuine timestamped strike.
- **Claim:** striking a pre-registered selection at a pre-registered pre-off moment
  `T_strike` (e.g. `off − 120 s`) on the live ladder yields **positive true CLV vs BSP**
  (`bsp/struck − 1 > 0`) that **beats a price-band × course-stratified null AND passes the
  Brier gate** (blend beats BSP), out of sample.
- **Kill:** CLV that is just the structural WAP→BSP drift of its price band (Test 4's
  named artifact) → PRICED. No Brier improvement → CLV-relative-only, not a forecast edge.

### Q4 (PROPOSED) — In-running back-to-lay scalp economics on the front-runner family
The natural complement to Q2: not "is there directional edge" but "**does the
mechanically predictable front-runner price path (shorten on an uncontested lead → layable
as it tires) produce a positive round-trip after realistic two-sided fills + 2% commission**."
- **Claim:** a pre-registered back-at-entry / lay-at-exit (or the reverse) round trip on
  the `led`-≤2.0 family clears **> 0 net of 2% commission and the §6 fill model on BOTH
  legs**, beats the price-band × course null by ≥ +1.0%, holdout-corroborated, with the
  hindsight-fill canary.
- **Kill:** positive only under one-sided/hindsight fills; round-trip ≤ null+tol; tail
  dominated by the rare flat non-completion (§3).

*(If your intended Q3/Q4 differ, paste them and I will swap them in verbatim before any
parse — nothing downstream depends on the proposed wording.)*

---

## 11. Global ordering & kill criteria

1. **Q1 (liquidity) gates everything.** FAIL → abandon in-running (Q2/Q4 not run).
2. **Q2 / Q4 (in-running edge / scalp)** run only on a Q1 PASS **+ fresh authorization**.
3. **Q3 (pre-off CLV)** is independent of Q1 (it is a pre-off question) but shares the
   stratified-null + Brier discipline; it may run in parallel once authorized.
4. Any question: **report the kill as the result.** No retune-to-pass, no post-hoc
   subpopulation narrowing, no moving `EDGE_TOL`/N/X/Y/`T_strike` after data contact.

---

## 12. Amendment log  *(append-only; each entry: date — what changed — why)*

### Amendment 1 — 2026-07-06 — Q1 closed; in-running retired; **pre-off gate program (Q2/Q3/Q6) defined**

**Why now / discipline:** Gate 1 (Q1) reconstructed full market streams (which include
pre-off ticks) but computed **only in-running liquidity** — no pre-off signal, CLV, fill,
or direction statistic was ever examined. So the pre-off questions below are still being
pinned **before first pre-off data contact**, and this amendment is written before any
pre-off gate is run. Gaps the source brief left open are filled with **ASSISTANT-SPECIFIED**
defaults (flagged inline), authorised by the user's "execute end-to-end" delegation and
overridable only by a further dated amendment.

**(1) Q1 (liquidity) — CLOSED / FAIL.** Gate 1 run (commit `82b9786`): n=1,618 qualifying
opportunities (< the N=2,000 floor — reported, not retuned); £100 matchable in 27.3% (back)
/ 18.7% (lay) at t+~1s, **median matchable ≈ £0**. Liquidity not demonstrated → the
in-running direction fails at its primary gate.

**(2) In-running program — RETIRED as moot.** Old **Q2 (in-running edge, §5)** and **Q4
(in-running back-to-lay scalp, §10)** were both gated behind Q1 liquidity (§11), which
failed → neither is run. The queued **"endogenous front-runner detector"** alternative
dies with Q1. No further in-running work.

**(3) PRE-OFF GATE PROGRAM — DEFINED.** Numbering per user: Q2 is **repurposed** to the
pre-off momentum question; Q3 stays pre-off CLV (frozen); Q6 is new. Universe unchanged
(GB flat, §3); fill model unchanged (§6, £100 within 1 tick, 2% commission); nulls are
price-band × course stratified (§9). Two gates: **Gate 1 = liquidity/fill feasibility**,
**Gate 2 = edge** (survivors only).

- **Q2 — pre-off ladder momentum → final-10-min direction.**
  - *Gate 1:* reconstruct book depth **T-10min → T-30s at 1s**; PASS iff £100 matchable
    within 1 tick in > 50% of qualifying race-moments (as §4/§6).
  - *Gate 2:* features at **T-10min** — WAP momentum, back/lay size-imbalance ratio,
    volume acceleration — predict the **sign** of the price move over T-10min→off. Split:
    **discovery = 2015-05-01…2015-12-31, holdout = 2016-01-01…2016-04-30, PLUS an
    odd/even-week interleave robustness split**; the verdict must hold on BOTH —
    **disagreement = FAIL**. Bar: net-2%-commission directional return **beats the
    band-stratified baseline drift by ≥ 2 ticks AND is > 0**.

- **Q3 — timestamped-strike CLV (FROZEN as committed, §10 Q3).**
  - *Gate 1:* entry at **T-10min quoting the 3rd-best-back rung**; exit when **2 ticks
    shorter OR at T-30s**; PASS iff £100 matchable within 1 tick in > 50% (as §4).
  - *Gate 2:* frozen rule; CLV vs BSP; **band-stratified null**; Brier corroboration (§1).

- **Q6 — pre-off passive quote (market-making).**
  - *Quote rule (ASSISTANT-SPECIFIED):* two-sided passive quote **joining the touch queue**
    (a back at the best-back price and a lay at the best-lay price), **size £100/side**,
    **posted at T-30min** on every qualifying GB-flat WIN runner, resting until fill or the
    T-10min hedge.
  - *Fill model (as briefed):* filled only when **cumulative traded volume through the
    quoted price after posting exceeds (prior resting queue ahead of us + our £100)** — no
    partial credit beyond actual traded volume.
  - *Hedge:* on fill, exit at **T-10min at the then-touch** (cross the spread, pay it).
    Unfilled quotes = no trade, zero cost.
  - *Gate 1 bar:* **fill RATE is the gate — < 10% of posted quotes ever fill ⇒ Q6 FAILS**
    (too few trades to matter).
  - *Gate 2:* P&L **net 2% commission; verdict vs zero AND vs the band-stratified null**.
    Diagnostic (report, not verdict): post-fill **adverse-selection curve** — price drift
    at **+5min / +30min / T-10min** after each fill, filled vs unfilled runners.

- **Common:** N target = **all** qualifying pre-off opportunities in the tars (every GB
  flat race has a T-10min moment; **report the count**, expect ≫2,000). **Secondary slices
  (ASSISTANT-SPECIFIED thresholds):** S1 = sprints (≤ 6f), S2 = small fields (≤ 8 runners),
  S3 = handicaps — reported for each **surviving** question, **Benjamini-Hochberg-corrected
  as one family**. Verdicts decided **before** any money logic; kills reported plainly.
  Compute protocol: checkpoint, estimate wall-time early, **stop and report if > 8h**.
  Output: `analysis/gate_preoff_report.md` + PROJECT_NOTES append.

### Amendment 2 — 2026-07-06 — **Q7 (non-runner repricing latency) defined + gated**

**Why now / discipline.** With the pre-off momentum/CLV/quote family closed (Amendment 1,
all FAIL), this pins a **new, orthogonal** pre-off question — an *event-driven* latency
mechanic rather than a standing-signal edge — **before first Q7 data contact**. Frozen
below verbatim from the user's four-part brief (2026-07-06); assistant-specified defaults
are flagged inline and overridable only by a further dated amendment. Universe unchanged
(GB flat, §3); fill model unchanged (§6, 1 s latency, cross-the-spread, cap at available
size, `betDelay` verified per market); commission **2%**.

**Scope of the announcement family (what is / isn't observable).** Of the pre-off
announcement family — **non-runner (NR) withdrawal, going change, jockey change** — **only
NR withdrawals are observable in the Betfair stream**: a runner's
`marketDefinition.runners[].status` transitions to `REMOVED` with a `removalDate` and an
`adjustmentFactor` (the reduction factor, RF). **Going and jockey changes emit no stream
event** (absent from `marketDefinition`) → **untestable on this data, excluded from Q7** —
recorded here so the omission is deliberate, not overlooked.

**Q7 — mechanism & the known adversary.** When a runner is removed, the remaining runners'
fair prices shift **instantly and by known RF arithmetic** (below). If the visible ladder
repopulates *slower* than 1-second-latency retail can act, the stale quotes are pickable
free money (e.g. back a survivor at its stale, too-long pre-removal odds before the ladder
shortens to fair). **Known adversary, pre-registered as the likely killer:** Betfair
**SUSPENDS** the market on a removal and **cancels all unmatched bets**, so the stale quote
may never be hittable — the mechanic can delete the opportunity *by design*. **Measuring
whether it does is itself the result:** Gate 1's diagnostics are the deliverable regardless
of PASS/FAIL.

**Frozen definition (locked before first NR data contact).**
- **Event:** a runner `status → REMOVED` in a **GB-flat WIN** market (§3), **pre-off**
  (before the in-play turn), with **`adjustmentFactor` ≥ 2.5%**. Sub-2.5% RFs are **not
  applied by Betfair** (no repricing implied) → excluded. `t` = the removal instant = the
  `publishTime` of the message carrying the `REMOVED` transition; `removalDate` recorded as
  a cross-check.
- **Pre-state:** full book snapshot at **t − 1 s**. **Post-states:** 1-second snapshots
  **t + 1 s → t + 300 s**.
- **Fair-adjustment benchmark (the "known RF arithmetic"; exact formula pinned).** For each
  remaining runner *i* with pre-removal price `P_pre,i` (**best-back at t − 1 s**; best-lay
  and mid recorded as sensitivities), the fair post-removal price is the
  **probability-renormalisation** price:
  > **`P_fair,i = P_pre,i × (1 − A)`**,  where `A = Σ(adjustmentFactor / 100)` over all
  > runners removed at the event.
  *Derivation (WIN-market RF applies to the price):* the removed runner's implied
  win-probability ≈ its `adjustmentFactor`; removing it renormalises every survivor's
  probability `p_i → p_i /(1 − A)`, and since `price = 1/p`, each survivor's price scales
  **down** by the common factor `(1 − A)` — the shift the ladder *should* jump to at t⁺.
  *Cross-check benchmark (reported, not primary):* Betfair's mechanical matched-bet
  reduction `P' = 1 + (P_pre − 1)(1 − A)` (applied to *already-matched* bets); agrees to
  first order, diverges most at short prices → **Q7 reports headline sensitivity to which
  benchmark is used.** *Assumption flagged:* proportional redistribution (removed
  probability spreads pro-rata); non-proportional redistribution is possible but is not a
  pre-registerable known-arithmetic benchmark.
- **Opportunity (the tradable):** at **t + k (k = 1…30 s)**, available size at a price
  **stale vs the benchmark by ≥ 2 Betfair ticks**, on **either side** (a survivor still
  offered to back ≥ 2 ticks longer than `P_fair`, or to lay ≥ 2 ticks shorter). **Entry** =
  take it at **1 s latency** (§6), **£50 cap per runner**. **Exit** = at the **touch at
  t + 300 s**. **P&L net 2% commission.**
- **Null:** identical entry/exit at **matched random non-NR moments**, **band-matched by
  price and time-to-off** — strips the ambient pre-off drift/spread a survivor's band gets
  anyway, so only the *removal-driven* stale-quote return survives.

**Mandatory diagnostics (Gate 1, reported regardless of verdict):** (i) fraction of NR
events where the market **suspends**; (ii) **suspension-duration distribution**; (iii)
fraction where the **unmatched book is wiped** (post-suspension depth at t + 1 s vs
t − 1 s); (iv) **time-to-book-repopulation** (until depth returns to **80%** of the
pre-removal level).

**Gates.**
- **Gate 1 — fillability / does the opportunity survive the mechanic (Part B).** Count
  qualifying NR events across the 12 tars (**report the count and the rate per raceday**;
  expect hundreds). **Fillability bar:** a stale-quote opportunity with **≥ £50 available**
  exists in **≥ 10%** of NR events → PASS; **otherwise FAIL — mechanically deleted**
  (suspension + unmatched-cancel), the pre-registered expected outcome.
- **Gate 2 — edge, survivors only (Part C).** Only if Gate 1 passes. **P&L vs the null**,
  on the committed splits (**discovery 2015-05–12 / holdout 2016-01–04, §7, PLUS the
  odd/even-week interleave**; verdict must hold on both — disagreement = FAIL). **Verdict
  decided before any money-narrative**, on holdout; discovery + parity for corroboration.

**Discipline inherited:** intra-race leakage rule (§1) — the benchmark uses only the t − 1 s
state + published AF, both known at the removal instant; **no look-ahead** to the converged
price. **Thin-N handling (§4):** widen nothing / lower nothing; if edge-leg events are few,
the *mechanic* (suspension/wipe) is near-deterministic Betfair policy and is decisively
characterised even on hundreds of events, while the *edge* leg is reported as
underpowered — never retuned to pass. Compute protocol: checkpoint, wall-time estimate
early, **stop and report if > 8 h**. Output: `analysis/gate_q7_nonrunner_report.md` +
PROJECT_NOTES append.

---

## 13. Non-goals / what is NOT happening under this commit

- No parsing/replay/fitting of PRO market content for gate work yet (this file governs it,
  it does not perform it).
- No live capital; no TPD/sectional purchase; no jumps.
- `Milestone_Eight_Tests_Summary.md` is **referenced but not yet created** — flagged for
  compilation from the PROJECT_NOTES Test 1–8 entries (offered, not assumed).
