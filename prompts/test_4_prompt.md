# CC Brief — Test 4: Lay-Side Selection (Free Experiment Catalogue)

Date: 03 Jul 2026. Runs entirely on existing data (`joined_gb_2018_2026.csv`,
wap/morning_wap/bsp already in the join). No new acquisition. No sectionals needed.

## Setup
```
cd ~/projects/racing_project        # native WSL shell, NOT //wsl.localhost/
source .venv/bin/activate           # or .venv313 if pandas missing
git checkout ui-editorial && git status   # confirm clean before starting
```
Run all Python via `.venv/bin/python`. Same train/val/holdout splits as every
prior test — do NOT re-split.

## The question (verbatim from Free_Experiment_Catalogue Test 4)
Stage-1's "value" picks drift out +31.66% vs +14.12% baseline — wrong side for
backing, exactly the right side for laying. **Does laying those selections
produce positive lay-CLV, out of sample, after the hardened verdict?**

## Two selection variants — run BOTH
- **V1 (the live question):** lay Stage-1/blend's current BACK-value picks
  (model_prob > market_prob by the existing margin). Rationale: captured drift.
- **V2 (classic lay-side):** lay horses the model says are OVERpriced
  (model_prob < market_prob by margin). Symmetric mirror; expected priced, but
  it's the control that tells us whether V1 is drift-capture or noise.

## Metric definitions (pin these in code + unit tests before scoring)
- **Lay-CLV per bet** = `bsp / struck − 1` (struck = wap). Positive when the
  price DRIFTED after our lay — we laid at a shorter (better) price than close.
- **Lay P&L, fixed liability** (preferred risk framing): liability L fixed;
  stake = L/(odds−1). Win (horse loses): +stake × (1 − commission). Lose (horse
  wins): −L. Report net of 5% commission (not 2%).
- Also report fixed-stake P&L for comparability with back-side runs.
- Extend `backtest/clv.py` or add `backtest/lay_clv.py` + tests mirroring
  `test_clv.py` — metric maths pinned first, same as day 1.

## Hardened verdict — the referee (both gates required for RULED-IN)
1. **Price-band-stratified null:** selection lay-CLV must beat **"lay ALL
   runners in the same BSP band"**, on val AND holdout. This is critical here:
   longshots systematically drift WAP→BSP, so a longshot-heavy lay selection
   inherits positive lay-CLV as pure FLB/timing artifact — the exact mirror of
   the trainer_course_sr false positive. The band-matched lay-all baseline is
   the whole test.
2. **Brier corroboration gate:** the blend must beat BSP on Brier restricted to
   the selection's holdout horses. A lay-CLV number with no probability edge
   behind it reads PRICED.

## Known artifact to expect and name
The +32% drift finding was measured morning_wap→wap→BSP on the same WAP struck
price. If V1's positive lay-CLV disappears against the band-matched lay-all
null, the drift was the band composition talking, not the model — write that as
the result, it is a real answer.

## Additional cuts (report, don't gate on)
- Lay-CLV by BSP band (1–2 / 2–3 / 3–6 / 6–12 / 12+): shows where any effect
  lives and whether it's monotone-in-price (artifact signature).
- Liquidity sanity: laying 12+ shots at size is not matchable in thin markets —
  note morning_vol where carried; flag any "edge" living entirely in bsp>12.
- Holdout only after val passes — standard discipline.

## Output
Append results to PROJECT_NOTES (same format as tests 1–8): selections count,
mean/median lay-CLV vs band-null, Brier gate result, verdict
PRICED / RULED-IN / ARTIFACT-NAMED. One paragraph max per variant.

## Guardrails
- No BSP or pos anywhere upstream of selection (leakage guard as before).
- No new features, no re-tuning Stage-1 — this scores EXISTING selections
  flipped to the lay side. Anything else is a different test.
- Git identity: set repo-local before any commit if still on personal email.