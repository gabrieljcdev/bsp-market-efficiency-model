# In-Running Betfair Trading — Stage 0 + Stage 1 Brief

Purpose: the ONE cheap, falsifiable test that decides whether this direction is
worth Stage 2+ (liquidity stress test, TPD position data, live prototype) or
should be closed per the research brief's option (c). Total spend: tens to low
hundreds of pounds, no infrastructure build, no live capital.

Do NOT skip to a build. Do NOT buy TPD position data yet. This is a PRICE-ONLY
backtest using Betfair's own historical data service.

---

## Stage 0 — Pre-register the claim BEFORE buying any data

Write down the precise, falsifiable rule and the pass/fail bar NOW, before
looking at a single tick of data. This is non-negotiable — it's the exact
discipline that made the pre-race work trustworthy (pre-registering the bar
before seeing results, same as the narrow-subpopulation probe). Deciding the bar
after seeing the backtest is how the trainer_course_sr mirage happened.

**Candidate falsifiable claim (adapt as needed, but commit to specifics):**
> "Reacting to an in-running price move of ≥N ticks within the 1-second bet
> delay window yields positive expectancy, net of 2% commission and a
> conservative fill model, at a stake of at least £X per race, across a sample
> of at least Y races."

Fill in N, X, Y now. Suggested starting point: N = a move of 20%+ in-running
price within a short window (e.g. 2-5 seconds), X = £10 (a stake that would
actually matter, not a token £1), Y = at least 200-300 races (enough for a
holdout split, mirroring the pre-race discipline).

**Also pre-register:** what counts as PASS (proceed to Stage 2) vs FAIL (stop,
adopt the research brief's option-c read). Suggested: FAIL if net expectancy is
≤0 OR if the achievable matched size at the modelled fill rate is trivially
small (e.g. can't get £10 matched in >50% of qualifying opportunities).

## Stage 1 — The backtest

### Data
- Buy Betfair Historical Data **PRO tier** (50ms intervals, full ladder + volume)
  from historicdata.betfair.com, for a representative sample of UK horse
  racing markets: mix festival + midweek/lower-grade, ≥200-300 races, matching
  the Y from Stage 0.
- Confirm cost before buying (per-market/per-time-period pricing; data is not
  re-purchasable once bought — get the sample size right first time).
- Confirm the market's actual `betDelay` field for the sample (research found
  UK racing is ~1 second, best-supported, but VERIFY per-market rather than
  assume — some sources cite 2s or more).

### Replay + rule
- Replay tick-by-tick (betfairlightweight in Python, or a licensed replay tool
  e.g. Time Machine/Market Replay if preferred).
- Implement the pre-registered rule from Stage 0 exactly as written — do not
  adjust the rule after seeing results. If it fails as specified, that IS the
  result; do not retune N/X/Y to find a pass (same discipline as "don't narrow
  a subpopulation after seeing a result" from the pre-race work).
- **Model the 1-second delay explicitly** — your simulated order does not reach
  the book until the delay elapses; the market can move against you in that
  window.
- **Model 2% commission** on net winnings, matching the project's existing
  clv.py convention where applicable.

### The fill model — the single biggest source of false positives (be conservative)
- Do NOT assume you get matched at the ltp (last-traded price) the instant your
  rule fires. Only count a fill when the price genuinely trades THROUGH your
  requested level in the replayed order book.
- Cap size at the actually-available matched volume at your level and moment —
  not an assumed infinite market.
- If unsure how conservative to be, err MORE conservative — an optimistic fill
  model is exactly what would manufacture a false positive here.

### Verdict
- Holdout split on the race sample (e.g. by date), same as every other test
  this project has run — don't just report in-sample performance.
- Report against the Stage-0 pre-registered bar, explicitly: PASS or FAIL, with
  the actual net expectancy, fill rate, and achievable size at £X stake.
- If FAIL: report it as FAIL. Do not retune the rule and re-run to find a
  version that passes — that's p-hacking the same way a narrowed subpopulation
  chosen after seeing results would be.

## What happens next, depending on result
- **FAIL** (expectancy ≤0, or trivial achievable size): stop here. This
  confirms the research brief's most-likely read (option c) with actual
  evidence rather than priors, and the ~£100-300 spend was the cost of a
  genuine answer — same value as the pre-race tests that came back PRICED.
- **PASS** (positive net expectancy AND non-trivial size, holding out of
  sample): proceed to Stage 2 (liquidity/size stress test at target stake
  across more of the sample) per the research brief, before any TPD spend or
  live capital.

## Guardrails carried from the rest of the project
- This is a price-only test of a MOMENTUM/reaction hypothesis — it does not
  test whether TPD position data would add anything. Don't conflate a FAIL here
  with "TPD is definitely useless too" — but also don't let a FAIL here justify
  jumping straight to buying TPD data hoping IT succeeds where price alone
  didn't; that's chasing the idea past its own evidence.
- Leakage risk is real even in a backtest: make sure the rule only ever uses
  price/volume information that existed AT THE SIMULATED MOMENT, never a later
  point in the same race's tick stream (the equivalent of the pre-race project's
  "strictly prior runs only" discipline, applied to time within a single race).
- The Expert Fee doesn't affect this stage's economics at all (it only bites
  above £25k/year lifetime profit) — don't let it discourage running Stage 1;
  it's only relevant if Stage 1-2 pass and you're deciding whether to scale.