# Phase 3 — Free Edge-Feature Proxies — Working Notes

Living log for the build described in `prompts/edge_feature_proxies.md`.
Newest entries at the **bottom** of each block. The goal of the whole phase is a
**cheap test of an expensive decision**: do free proxies (pace, race-shape, sire)
move Stage-1's weight in the Benter blend off its current **~3%**? If yes → paid
data (TPD sectionals / Weatherbys pedigree) is justified. If no → we saved the spend.

**The one number we are chasing:** Stage-1 MODEL WEIGHT in the Stage-2 blend
(currently a ≈ 0.026 vs market b ≈ 0.98). Secondary readouts: Brier / log-loss
vs BSP. **NOT CLV** (still on the noisy LTP stand-in).

---

## Orientation (before Block 0) — DONE

Read: `PROJECT_NOTES.md`, both memory files, `models/stage1_logit.py`,
`models/stage2_blend.py`, the joined/form data headers, rpscrape vendor.

What the codebase actually is right now:
- **Data**: only Sept-2025 exists. `data/joined/joined_gb_2025_09.csv` = 7,979
  runners (29 race days) with form features + Betfair BSP. This is the **scored
  set** and stays Sept-2025 only.
- **Models**: pure-Python conditional logit, no numpy/sklearn.
  - Stage 1 (`stage1_logit.py`): features `or, draw, lbs, age`. `rpr` excluded
    (post-race leakage). Hard leakage guard (whitelist + blacklist asserts).
  - Stage 2 (`stage2_blend.py`): Benter blend of log(model_prob)+log(pre-off
    LTP market_prob). Learned **a≈0.026 (model) vs b≈0.98 (market)** → model is
    ~3% of the blend. This is the number Phase 3 is trying to move.
- **Scraper**: `vendor/rpscrape` produces per-day GB CSVs in
  `data/region/gb/all/YYYY_MM_DD.csv`. Invoked `./rpscrape.py -d 2020/10/01 -r gb`
  (a date) or `./rpscrape.py -r gb -y 2019 -t flat` (a whole year by type).
  Needs RP creds in `vendor/rpscrape/.env` (EMAIL + ACCESS_TOKEN, user-supplied).

### Two things to flag to the USER before building

1. **Block 0 not done — still on the slow path.** `pwd` returns
   `//wsl.localhost/Ubuntu-22.04/...` (the Windows UNC boundary path the brief
   warns about). Block A is a days-long file-heavy scrape; doing it over this
   path is exactly what Block 0 says to fix first. **Action is the USER's**:
   relaunch `claude` from a native WSL shell (`pwd` → `/home/gabriel/...`).

2. **Three files the brief told me to read do not exist** in the repo:
   `Day_Summary_18Jun.md`, `Feature_Catalogue.docx` (§3 pace, §4 pedigree),
   `Data_Sources_Reference.docx`. I substituted `PROJECT_NOTES.md`, the two
   memory files, and the existing prompt briefs. If those docx files exist
   elsewhere (e.g. not synced into WSL), point me at them — §3/§4 of the
   Feature Catalogue is the intended spec for the pace & pedigree features.

### Good news — the running-style data source is already in hand

No GPS, no in-running-position column (consistent with the brief's guardrail:
direction-only proxy, not magnitude). BUT the form **`comment`** field is rich
free-text running commentary, e.g.:
- *"Travelled strongly - in touch with leaders - headway over 3f out - led over 1f out"*
- *"Prominent - pressed leader over 3f out"*
- *"Dwelt start - in rear - hung left"*

This is a clean source for a **direction tag** (led / prominent / midfield /
held-up / rear) via keyword parsing — arguably better than reconstructing early
position. This is the Block C proxy. It is honestly a PROXY (direction, not a
fabricated sectional figure), which is what the brief demands.

---

## Block 0 — Fix the WSL path  → **BLOCKED ON USER (gate FAILED)**

Gate check the user asked for (run before Block A):
```
pwd → //wsl.localhost/Ubuntu-22.04/home/gabriel/projects/racing_project   (FAIL)
df  → df: cannot stat '..': No such file or directory                     (FAIL — can't resolve path)
```
Both fail. This session is the Windows-side `claude` CLI pointed at the UNC
boundary path; can't be fixed from inside the session. User must relaunch
`claude` from a native WSL shell (VS Code WSL terminal or `wsl`), cd into the
project, `source .venv/bin/activate`, then relaunch. STOPPED per the user's
instruction ("if pwd shows //wsl.localhost/ ... stop and tell me before scraping").

Pre-set per user answers: feature spec = use the brief's spec (proceed without
the missing docx); Block A start = **confirm RP creds first**, then small window,
then full pull. Resume point after path fix: re-run the gate check → verify
`vendor/rpscrape/.env` ACCESS_TOKEN works.

## Block A — Deep history scrape (2018→present, flat+jumps)  → not started
## Block B — As-of windowing engine + leakage test  → not started
## Block C — Running style + pace map (from `comment`)  → not started
## Block D — Sire going/distance proxy  → not started
## Block E — Re-fit, re-blend, read the ONE number  → not started
