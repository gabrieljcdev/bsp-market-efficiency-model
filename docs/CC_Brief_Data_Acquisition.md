# CC Brief — Data Acquisition (Day Plan Blocks 1–4)

**For: Claude Code, working in `~/projects/racing_project` with `.venv` active.**
**Goal:** get free Betfair closing-line data (with BSP) and free Racing Post
form data flowing, then joined per runner. Zero spend. This is the dataset
everything downstream (the model, the CLV harness) depends on.

Read `README.md`, `parsers/parse_bsp.py`, and `One_Day_Data_Plan.docx` first
for context. Work block by block. After each block, stop and report what you
got (row counts, a sample, any errors) before moving on — do not run the
whole thing unattended.

---

## Guardrails (important)

- **Do not place any bets, log into Betfair to bet, or call any live betting
  endpoint.** This is data download and local processing only.
- **Credentials:** rpscrape now needs a Racing Post login token, and Betfair
  needs the user's account login. The USER enters all credentials themselves.
  Do not ask for or store passwords in plain text. The `.env` file holds
  tokens the user pastes in; make sure `.env` is in `.gitignore`.
- The user wants to understand each step. Briefly explain what each command
  does before running it, and surface anything surprising.
- BSP is the scoring benchmark, never a model input. Keep it out of any
  feature table you build here — it belongs only in the BSP table.

---

## Block 1 — Betfair free-tier data (verify access)

The free closing-line source is the FREE tier at `historicdata.betfair.com`,
accessed with the user's normal free Betfair account. It carries BSP and
per-minute last-traded price (no volume, no full ladder — fine for our needs).

This block is mostly the user's manual task (it's a website with a login). Your
job: confirm the user knows the exact filter to use, and be ready to receive
the downloaded files.

Tell the user to download, via the custom Download Data filter on the My Data
page:
- Sport = Horse Racing
- Country = GB
- Market type = WIN
- File type = M (market data)
- Plan = FREE
- One month at a time (Betfair recommends this; large ranges time out)

Files arrive as `.tar` / `.tar.bz2` of JSON in the Exchange Stream format —
the same format `parse_bsp.py` already reads. They go in `data/historical/`.

**Report:** confirm at least one real GB WIN file is in `data/historical/`.

---

## Block 2 — Extend the parser & build the BSP table

Extend `parsers/parse_bsp.py` with two changes, then run it over the month.

1. **Walk archives.** Add handling so the parser can take a `.tar` or
   `.tar.bz2` path, iterate its member files, and feed each to
   `parse_stream()`. (See `vendor/autoHubTutorials/processingTarFiles101` for
   a reference pattern.) The existing single-file logic must keep working.
2. **Filter to horse racing.** Only keep markets where the market definition
   `eventTypeId == 7` (horse racing). NOTE: the bundled real fixtures in
   `data/samples/real_format_fixtures/` are eventTypeId 4339 (greyhounds) —
   they are format tests only and will be filtered OUT by this rule, which is
   correct. Test the archive-walking on them, but expect zero horse-racing
   rows from them.
3. Run over `data/historical/`, write a combined `output/bsp_table.csv`.

**Sanity checks to run and report:**
- Do favourites have short BSP and longshots long? (eyeball a few races)
- Does each race's sum of (1/BSP) land near 1.0–1.05 (a near-fair book)?
  A sum far above that means missing/!ACTIVE runners or a parse problem.
- Row count, and runners-per-race distribution.

---

## Block 3 — rpscrape form data

rpscrape is in `vendor/rpscrape`. **It has changed recently — check before
assuming the bundled copy is current:**

- It now requires **Python 3.13+** and these deps:
  `pip3 install curl_cffi jarowinkler lxml orjson python-dotenv tomli tqdm`
- It now requires **authentication**. The user must log in to the Racing Post
  site and copy two values from their browser cookies into a `.env` file in
  the rpscrape root:
  ```
  EMAIL=their@email.com
  AUTH_STATE=...            (auth_state cookie)
  ACCESS_TOKEN=...          (the CognitoIdentityServiceProvider...accessToken value)
  ```
  This is a manual step for the USER. Walk them through opening dev tools →
  storage/cookies, but they extract and paste the values themselves.
- If the bundled copy looks older than this (no `.env` auth, no racecards.py),
  consider re-cloning the latest from `https://github.com/joenano/rpscrape`.

**Command syntax (current):**
- A date + region:  `./rpscrape.py -d 2020/10/01 -r gb`
- A whole year by type:  `./rpscrape.py -r gb -y 2019 -t flat`
  (for jumps, the year is the SEASON START — 2018 covers the 2018–19 season)

Scrape GB results for the SAME period your Block 2 BSP files cover. Start with
a SMALL window (a few days) to prove auth + output work before pulling a whole
month — it scrapes Racing Post pages and can be slow / rate-limited; be gentle.

Confirm the output CSV includes at least: date, course, race time, horse name,
finishing position, RPR, Topspeed, and ideally a horse/race id. Save under
`data/form/`.

**Report:** the form CSV path, row count, and the column list.

---

## Block 4 — Join form + BSP (the hard part)

The two sources share no clean key, so join on race + horse. Horse-name
formats differ between Betfair and Racing Post (country suffixes like "(IRE)",
punctuation, and Betfair names often carry a leading cloth number e.g.
"1. Buck"). Expect this to be fiddly.

Write `parsers/join_form_bsp.py` (or similar) that:
1. Normalises horse names on BOTH sides: strip leading cloth numbers, strip
   country suffixes "(IRE)/(USA)/..." , remove punctuation, collapse spaces,
   uppercase. Keep the raw name too for debugging.
2. Builds a race key from date + course + (off time or race number). Course
   names will differ between sources — may need a small mapping table.
3. Joins on race key + normalised name.
4. **Reports the match rate**, and dumps unmatched rows from each side to a
   file so the user can inspect the format quirks and iterate.
5. Writes the joined table to `data/joined/` — one row per runner with the
   form features AND its BSP.

Do NOT expect 100% matches. Aim for a high majority, log the rest. A clean
sample beats a big messy join.

**Report:** match rate, joined row count, and a sample of 5 joined rows plus
5 unmatched ones.

---

## Done = the foundation for everything else

When Block 4 produces a joined table (form features + BSP per runner), the data
foundation is complete. The next phase (not in this brief) is:
- `backtest/clv.py` — the CLV scoring harness
- the two-stage model (fundamental conditional logit, then blend with market price)

Stop after Block 4 and report the joined dataset. Don't start the model.
