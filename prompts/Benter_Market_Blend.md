# CC Brief — Stage-2 Benter Market Blend (Blocks D1–D3)

**For: Claude Code, working in `~/projects/racing_project` with `.venv` active.**
**Goal:** build the Stage-2 blend — combine the Stage-1 model's probability with
the market-implied probability (Benter's two-stage method), inspect the learned
weights, then calibrate and CLV-score the blend three-way against Stage-1-alone
and BSP. This proves the blend machinery end-to-end; it is a concept demo, not a
real-edge result (see "Honest framing" below).

**Session-start fix (do this first):** `pwd` currently returns a
`//wsl.localhost/...` Windows path. Confirm you are in a native WSL shell —
`pwd` should return `/home/gabriel/projects/racing_project`. If it shows the
`//wsl.localhost/` form, the shell was launched from the Windows side; flag it
and use native paths. Do not write outputs through the UNC path.

Read `PROJECT_NOTES.md`, `Day_Summary_16Jun.md`, `models/stage1_logit.py`,
`models/score_stage1_clv.py`, and `backtest/clv.py` first. Work block by block.
**After each block, STOP and report** before moving on.

---

## Guardrails (read before writing any code)

- **The cardinal leakage rule, restated for Stage 2:** the market input to the
  blend MUST be the **pre-off price** (the `bf_last_preoff_ltp` LTP stand-in
  already used in Block C), NEVER **BSP**. BSP is the scorer. Blending BSP in
  would be leakage — you'd be feeding in the answer you are trying to beat.
- **Build an explicit guard:** assert that the Stage-2 feature matrix contains
  only the two intended inputs (model prob term + pre-off-market prob term) and
  that neither `bsp`/`bsp_implied_prob` nor `pos` nor any post-race column is
  among them. Hard-fail otherwise. Print the exact inputs used.
- **Recall the Block-C resolution finding:** Stage 1 is under-confident / low
  resolution (bunches predictions near the ~11% base rate). The pre-off market
  price is far sharper and sits very close to BSP. So expect the blend to lean
  heavily on the market term and only lightly on the model — that is the
  expected, honest outcome, not a bug.
- Keep it readable and commented; the user must be able to explain the learned
  weights back. Fixed random seed. Native WSL paths only. Local modelling only —
  no bets, no live endpoints.

---

## Block D1 — Build the blend

**Input:** `models/stage1_scored.csv` (per-runner `model_prob`, plus the
carried non-feature columns including the pre-off LTP and bsp/pos).

Write `models/stage2_blend.py` that:

1. **Derives the market-implied probability** from the pre-off price:
   `raw = 1 / bf_last_preoff_ltp` per runner, then **renormalise within each
   race** so the per-race probabilities sum to 1.0 (the raw 1/LTP across a field
   sums to >1 because of the book's overround — divide each by the race's sum).
   Call this `market_prob`. Handle missing/zero LTP explicitly (log how many
   runners affected; drop or impute and state which).
2. **Two inputs only**, in the form Benter's method uses — the log-probabilities:
   `x1 = log(model_prob)`, `x2 = log(market_prob)`. (Logs because the conditional
   logit's softmax is exponential; logging the probs makes the blend a weighted
   geometric mean of the two, which is the standard Benter formulation. Comment
   this so the user sees why.)
3. **Fits a Stage-2 conditional/multinomial logit grouped by race** on `[x1, x2]`,
   predicting the actual winner — the same per-race choice-set structure as
   Stage 1. Output: a `blend_prob` per runner that **sums to 1.0 within each
   race** (report min/max/mean of the per-race sums — expect ≈ 1.000).
4. **Leakage assertion** as above: inputs are exactly `{x1 from model, x2 from
   pre-off market}`; assert no BSP/pos/post-race column present. Print inputs.
5. Writes `models/stage2_scored.csv` — keep race key, horse, `model_prob`,
   `market_prob`, `blend_prob`, and bsp/pos carried as NON-features (clearly
   separated, never inputs).

**Report:** rows processed, missing-LTP count and handling, per-race sum check,
confirmation of the leakage guard, and the printed input list. STOP.

---

## Block D2 — Inspect the learned weights (the payoff moment)

This is the conceptual core — do not skip or bury it.

Print the two fitted Stage-2 coefficients (the weights on `x1 = log model_prob`
and `x2 = log market_prob`) plainly, and interpret them in one or two lines:

- A large weight on `x2` (market) and a small weight on `x1` (model) means the
  blend is mostly trusting the market and your model added only a sliver — the
  expected result for a public-feature Stage 1.
- A weight on `x1` at or below ~0 means your model added nothing (or worse) once
  the market price is known.
- A meaningful positive weight on `x1` would mean your model carries independent
  information the market underweighted — surprising here, and if seen, treat with
  suspicion (check the market input isn't accidentally BSP-like / leaking).

**Report:** the two coefficients, their ratio, and the one-line interpretation:
"did the Stage-1 model add anything the pre-off market didn't already have?"
STOP.

---

## Block D3 — Calibrate & CLV the blend, three-way

Reuse the existing harnesses (`models/calibrate.py`, `backtest/clv.py` via
`models/score_stage1_clv.py`'s approach). Produce a **three-way** comparison:
**Stage-1-alone vs Blend vs BSP.**

1. **Proper scores:** Brier and race log-loss for `model_prob`, `blend_prob`,
   and `bsp_implied_prob` on one table (lower = better). The key question:
   **does the blend beat Stage-1-alone?** (Adding the market should help —
   expect blend's Brier/log-loss between Stage-1 and BSP.)
2. **CLV:** run the value-selection + CLV scoring on the BLEND's probabilities,
   exactly as Block C did for Stage 1 (back where `blend_prob > 1/struck`; struck
   = pre-off LTP stand-in, never BSP; net 5% commission). Report selections,
   mean CLV, % beating BSP, and put it beside Stage 1's Block-C numbers
   (mean CLV −0.38%, beats close 36.8%).

**Honest expectation — state whether the evidence matches it:**
- Blend should **beat Stage-1-alone** (lower Brier/log-loss, CLV closer to zero).
- Blend should **approach but NOT beat BSP** — because the market input (pre-off
  LTP) is already a near-BSP price, so the blend can at best get close to the
  scorer. **Beating BSP here is a red flag**, not a triumph: first suspect the
  LTP↔BSP timing gap leaking through (the artifact already documented in
  PROJECT_NOTES), not genuine edge.

**Report:** the three-way proper-scores table, the CLV comparison table, and a
plain verdict: did the blend beat Stage 1? did it approach BSP? any red flags?

---

## Honest framing — keep this in the wrap-up

This Stage 2 proves the **machinery** of the Benter blend, not a real edge,
because: (a) Stage 1's only real ability feature is OR (imputed for 1,459
runners — low resolution), and (b) the market input is the free-tier LTP
stand-in, not a real timestamped struck price. Real Stage-2 value needs Tier-1
edge features (sectionals, pedigree) feeding a Stage 1 that has genuine
resolution — that is Phase 3, not today. Today's win is the end-to-end pipeline:
Stage 1 → market blend → calibrated → CLV-scored three-way, leakage-free.

---

## Wrap-up

When D1–D3 are done and reported, write a one-line status into `PROJECT_NOTES.md`
(newest at top): blend built, learned weights (model vs market), whether blend
beat Stage 1, whether it approached BSP, any red flags. List every file created.
Stop there — do not start Phase 3 edge features.

**Final report:** the three checkpoint outputs (per-race sum, learned weights,
three-way Brier/log-loss + CLV) and the paths of every file created.