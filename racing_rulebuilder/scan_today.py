"""
scan_today.py -- Stage 3 scanner (Tier 1).

Take a VALIDATED selection rule and flag horses that qualify in TODAY's racecards.
Same filter logic and leakage discipline as run_strategy.py -- literally the same
functions (_eval_node / check_fields / load_manifest_sets) -- but pointed at the
rpscrape racecard pull instead of the 726k historical joined set.

WHY THIS IS DIFFERENT FROM THE HISTORICAL CASE
----------------------------------------------
On today's cards the race HAS NOT RUN. The post-race / market columns the
historical pages carry -- pos, secs, dec, rpr(result), bsp, wap, pre/ip prices,
finishing data -- DO NOT EXIST. The scanner therefore:
  * builds ONLY pre-race selection-input columns from the card (CARD_COLUMNS),
  * never maps any racecard field onto a settled-price column,
  * rejects (via the manifest leakage guard) any rule that references a post-race
    column, with a message that says it does not exist yet,
  * keeps DISPLAY columns (what a human reads) separate from SELECTION-INPUT
    columns (what the rule evaluates) -- same separation as the historical pages.

NB the rpscrape Runner model contains no price field at all, so there is no
forecast/morning price here to mistake for a settled one. Tier 1 is purely:
validated rule -> today's qualifying races. (Live-CLV vs a model number is Tier 2+.)

USAGE
-----
    # pull today's GB cards first (rpscrape, needs auth + its py3.13 venv):
    #   cd vendor/rpscrape/scripts && python racecards.py --day 1 --region gb
    python3 scan_today.py --strategy strategy.json [--date YYYY-MM-DD | --cards FILE] [--out scan.json]
"""
import os
import sys
import json
import argparse
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
import run_strategy as rs        # reuse the EXACT filter + leakage machinery

# Standard places rpscrape / this tool may drop the daily card file.
CARD_DIRS = [
    os.path.join(_ROOT, "vendor", "rpscrape", "racecards"),
    os.path.join(_HERE, "racecards"),
    os.path.join(_ROOT, "racecards"),
]

# Pre-race selection-input columns we can build from a racecard, mapped onto the
# historical column names so the SAME rules apply. (sex_rest has no card source.)
CARD_COLUMNS = {
    "date", "region", "course", "course_detail", "off", "race_name", "type",
    "class", "pattern", "rating_band", "age_band", "dist", "dist_f", "dist_m",
    "going", "surface", "ran", "prize", "num", "draw", "horse", "age", "sex",
    "lbs", "hg", "jockey", "trainer", "or", "sire", "dam", "damsire", "owner",
}


def _metres(card):
    y, f = card.get("distance_y"), card.get("distance_f")
    if y:
        return round(y * 0.9144)
    if f:
        return round(f * 201.168)
    return None


def _race_inputs(card):
    """Race-level pre-race fields shared by every runner (historical names)."""
    return {
        "date": card.get("date"),
        "region": card.get("region"),
        "course": card.get("course"),
        "course_detail": card.get("course_detail"),
        "off": card.get("off_time"),
        "race_name": card.get("race_name"),
        "type": card.get("race_type"),
        "class": card.get("race_class"),
        "pattern": card.get("pattern"),
        "rating_band": card.get("rating_band"),
        "age_band": card.get("age_band"),
        "dist": card.get("distance"),
        "dist_f": card.get("distance_f"),
        "dist_m": _metres(card),
        "going": card.get("going"),
        "surface": card.get("surface"),
        "ran": card.get("field_size"),
        "prize": card.get("prize"),
    }


def _runner_inputs(base, r):
    """Per-runner pre-race SELECTION-INPUT row (historical column names)."""
    row = dict(base)
    row.update({
        "num": r.get("number"),
        "draw": r.get("draw"),
        "horse": r.get("name"),
        "age": r.get("age"),
        "sex": r.get("sex") or r.get("sex_code"),
        "lbs": r.get("lbs"),
        "hg": r.get("headgear"),
        "jockey": r.get("jockey"),
        "trainer": r.get("trainer"),
        "or": r.get("ofr"),                 # officialRatingToday -> pre-race 'or'
        "sire": r.get("sire"),
        "dam": r.get("dam"),
        "damsire": r.get("damsire"),
        "owner": r.get("owner"),
    })
    return row


def _runner_display(card, r):
    """Human-facing DISPLAY row -- deliberately separate from the input row, and
    deliberately price-free (no settled or forecast price is shown as a price)."""
    return {
        "no": r.get("number"), "horse": r.get("name"), "draw": r.get("draw"),
        "age": r.get("age"), "sex": r.get("sex") or r.get("sex_code"),
        "lbs": r.get("lbs"), "or": r.get("ofr"), "form": r.get("form"),
        "hg": r.get("headgear"), "jockey": r.get("jockey"), "trainer": r.get("trainer"),
    }


def _runner_rows(card):
    """(input_row, display_row) per ACTIVE runner; non-runners/reserves excluded."""
    base = _race_inputs(card)
    rows, excluded = [], 0
    for r in card.get("runners", []):
        if r.get("non_runner") or r.get("reserve"):
            excluded += 1
            continue
        rows.append((_runner_inputs(base, r), _runner_display(card, r)))
    return rows, excluded


def scan(strategy, cards):
    """Apply the rule to a {region:{course:{off: racecard}}} structure."""
    rules = strategy.get("selection_rules") or {"combinator": "all", "children": []}
    post_race, derived = rs.load_manifest_sets()
    referenced = rs._collect_fields(rules, set())
    fc = rs.check_fields(referenced, CARD_COLUMNS, post_race, derived)

    res = {"ok": False, "field_check": fc, "errors": []}
    if fc["leakage"]:
        res["errors"].append(
            "post-race column(s) referenced -- these do NOT exist on a racecard "
            "(the race has not run): " + ", ".join(fc["leakage"]))
    if fc["unsupported_derived"]:
        res["errors"].append(
            "derived feature(s) not available on racecards: "
            + ", ".join(fc["unsupported_derived"]))
    if fc["unknown"]:
        res["errors"].append(
            "column(s) not produced from racecards (e.g. sex_rest, or a typo): "
            + ", ".join(fc["unknown"]))
    if res["errors"]:
        return res

    races = []
    n_races = n_qual = n_excluded = 0
    for region, courses in cards.items():
        for course, offs in courses.items():
            for off, card in offs.items():
                n_races += 1
                rows, excluded = _runner_rows(card)
                n_excluded += excluded
                quals = [disp for inp, disp in rows if rs._eval_node(rules, inp)]
                if quals:
                    n_qual += len(quals)
                    races.append({
                        "region": region, "course": card.get("course", course),
                        "off": card.get("off_time", off), "race_name": card.get("race_name"),
                        "type": card.get("race_type"), "class": card.get("race_class"),
                        "going": card.get("going"), "dist": card.get("distance"),
                        "field_size": card.get("field_size"),
                        "active_runners": len(rows), "n_qualifiers": len(quals),
                        "qualifiers": quals,
                    })

    races.sort(key=lambda r: (str(r["off"]), str(r["course"])))
    res.update(ok=True, races=races, n_races_scanned=n_races,
               n_races_with_qualifier=len(races), n_qualifiers=n_qual,
               n_nonrunners_excluded=n_excluded)
    return res


# --------------------------------------------------------------------------- #
# Card-file resolution + CLI.                                                  #
# --------------------------------------------------------------------------- #
def find_cards(date_str, explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    for d in CARD_DIRS:
        p = os.path.join(d, f"{date_str}.json")
        if os.path.exists(p):
            return p
    return None


def _print(res, date_str, path):
    if not res["ok"]:
        print("SCAN NOT RUN:")
        for e in res["errors"]:
            print("  -", e)
        return
    print(f"Scan {date_str}  (source: {os.path.relpath(path, _ROOT)})")
    print(f"  {res['n_races_with_qualifier']}/{res['n_races_scanned']} races have a qualifier "
          f"-- {res['n_qualifiers']} runner(s); "
          f"{res['n_nonrunners_excluded']} non-runner/reserve excluded.")
    print("  (racecards are pre-race only: no pos/bsp/wap/rpr-result exist yet.)")
    for r in res["races"]:
        print(f"\n  {r['off']}  {r['course']} -- {r['race_name'] or ''} "
              f"[{r['type'] or '?'}, {r['going'] or '?'}, {r['dist'] or '?'}]  "
              f"({r['n_qualifiers']}/{r['active_runners']} qualify)")
        for q in r["qualifiers"]:
            print(f"     #{q['no']:<3} {str(q['horse'])[:24]:<24} "
                  f"or {q['or']}  age {q['age']}  {q['jockey'] or ''} / {q['trainer'] or ''}")


def main():
    ap = argparse.ArgumentParser(description="Stage 3 scanner -- rule -> today's qualifying races.")
    ap.add_argument("--strategy", required=True, help="strategy.json with selection_rules")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--cards", help="explicit path to a racecards JSON file")
    ap.add_argument("--out", help="write scan results JSON here")
    args = ap.parse_args()

    date_str = args.date or datetime.date.today().isoformat()
    path = find_cards(date_str, args.cards)
    if not path:
        looked = "\n    ".join(os.path.join(d, f"{date_str}.json") for d in CARD_DIRS)
        print(f"No racecard file for {date_str}. Looked in:\n    {looked}\n"
              "Pull it first:  cd vendor/rpscrape/scripts && "
              "python racecards.py --day 1 --region gb")
        sys.exit(1)

    strategy = json.load(open(args.strategy))
    cards = json.load(open(path))
    res = scan(strategy, cards)
    _print(res, date_str, path)
    if args.out:
        json.dump(res, open(args.out, "w"), indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
