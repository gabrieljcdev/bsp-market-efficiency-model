# CC Brief — Diagnostic: Are `rpr` and `or` Pre-Race or Post-Race?

**For: Claude Code, working in `~/projects/racing_project` with `.venv` active.**
**Goal:** determine, with evidence, whether the `rpr` and `or` columns in the
joined dataset are PRE-RACE (the value carried into the race, legitimate as a
model input) or POST-RACE (assigned/updated from the result, leakage). This
gates Block B. **Read-only diagnostic — do NOT re-scrape, do NOT rebuild the
model, do NOT modify the joined data.**

Context: in Block A you found the highest-`rpr` horse wins 72.9% of races and
excluded `rpr` as post-race leakage, replacing it with `or` (highest wins 23%).
Before scoring the model in Blocks B/C we need to confirm two things:
1. Is `rpr` post-race *by nature* (correct exclusion, no fix needed), or is it
   post-race because of a *join/alignment bug* (a fixable error)?
2. Is `or` — the model's only real ability feature — genuinely pre-race, or is
   it contaminated by the same mechanism?

---

## The core test — does the rating move WITH the race's own result?

A pre-race rating is fixed before the off and cannot know the finishing position.
A post-race rating moves with how the horse ran that day. So:

**For both `rpr` and `or` separately, test the within-race correlation between
the rating and the finishing position (`pos`).**

- A pre-race rating should correlate with `pos` only WEAKLY/indirectly (better
  horses tend to finish higher, but the rating was set in advance and contains no
  same-race result info).
- A post-race rating will correlate STRONGLY with same-race `pos`, because the
  rating was derived from that finish.

Report, per rating column:
1. The fraction of races where the **highest-rated runner won** (you have this
   for both already: rpr 72.9%, or 23% — re-confirm).
2. The fraction of races where the **highest-rated runner finished in the top 3**.
3. Within-race rank correlation between the rating and `pos` (e.g. average, per
   race, of the Spearman/rank correlation between rating-rank and finish-rank).
   Strong negative (high rating ↔ low/winning finish position) = result-driven.

---

## The decisive test — same horse, consecutive runs

This is the cleanest discriminator. Many horses run more than once in the
September data.

For horses with ≥2 runs in the dataset, line up their runs in date order and ask:
**does the rating attached to run N reflect run N's result, or run N−1's?**

- **Pre-race behaviour:** the rating on run N should be knowable before run N —
  i.e. it should look like a function of the horse's history UP TO N−1, and
  should NOT jump in lockstep with run N's own finishing position.
- **Post-race behaviour:** the rating on run N moves with run N's own `pos` — a
  good run N spikes the run-N rating, a bad one drops it. That's the leak.

Concretely, for a sample of (say) 30 horses with multiple runs, print a small
per-horse table:

```
horse | run_date | pos | rpr | or | (rpr change vs prev run) | (prev run's pos)
```

Then state plainly: does `rpr` (and separately `or`) on a given run track THAT
run's `pos`, or the PREVIOUS run's? If a strong run N is accompanied by a
same-row rating spike, that rating is post-race for that row.

---

## Cross-check — where does each column come from?

Briefly confirm provenance from the existing pipeline (no re-scrape):
- `rpr`: rpscrape pulls Racing Post **results** pages. The RPR on a results page
  is RP's **performance** rating for that run — inherently post-race. Confirm
  this is the field we have (vs any racecard/forecast rating, which would be
  pre-race). State which.
- `or`: the BHA **Official Rating** / handicap mark. By nature this is the mark
  carried INTO the race (pre-race), but confirm the joined column wasn't sourced
  from a post-race/updated mark and isn't misaligned by the join.

---

## The two outcomes and what each means

State explicitly which conclusion the evidence supports, for EACH column:

- **Possibility 1 — post-race by nature (expected for `rpr`):** the column is
  correct data, just a post-race quantity. Correct action = keep it excluded as
  a feature; NO fix to collection needed. If this is `rpr`, Block A's exclusion
  was right and we proceed.
- **Possibility 2 — join/alignment bug:** ratings are misattributed to the wrong
  run (e.g. result-row rating landed on the same row as the result). This is a
  FIXABLE error — and critically, if it affects `or` too, then `or` is also leaky
  and the Block A model is built on a contaminated feature. If this is the case,
  STOP — do not proceed to Block B until fixed.

**The decision that matters most:** is `or` clean? If `or` is genuinely pre-race
and uncontaminated, the model is safe to score (Blocks B/C) as built. If `or`
shows the same result-tracking as `rpr`, the model's only real feature is leaky
and we fix before scoring.

---

## Report

1. The two within-race tables (highest-rated win% / top-3%, and rank correlation
   with `pos`) for `rpr` and `or`.
2. The per-horse consecutive-runs sample table.
3. A one-line verdict per column: PRE-RACE (safe) / POST-RACE-BY-NATURE (exclude,
   no fix) / JOIN-BUG (fix before proceeding).
4. A clear go / no-go for Block B.

Do not change any data or code in this pass. Diagnose and report only.