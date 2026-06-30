#!/usr/bin/env python3
"""build_course_geometry.py -- compile the static course-geometry reference table.

One row per DISTINCT course-name string in data/joined/joined_gb_2018_2026.csv.
The course name is the JOIN KEY, so each row's name must BYTE-MATCH a value in the
joined set exactly (a near-miss spelling joins to nothing -- the same trap that
bit the weather course map). This script validates that match both ways and
refuses to write a table with any unmatched / missing course.

TWO RELIABILITY TIERS (see the per-row `tier2_verified` flag):

  TIER 1 -- unambiguous published facts, drafted for spot-check:
    handedness        Left | Right | Figure-of-eight
    course_shape      Oval | Triangular | Horseshoe | Pear | Round | Figure-of-eight
    circumference_f   round-course length, furlongs (approx published figure)
    run_in_y          run-in length, yards, WHERE KNOWN (blank = not filled, no guess)

  TIER 2 -- descriptive / source-dependent, drafted as PROPOSED (verified=false):
    course_character  Galloping | Sharp | Stiff
    undulation        Flat | Undulating
    uphill_finish     Yes | No
  Every Tier-2 value here is UNVERIFIED. `tier2_verified` is "false" on every row
  until a human confirms the judgement calls; nothing downstream should trust the
  Tier-2 fields for analysis until that flag flips.

Run:  python3 data/reference/build_course_geometry.py
"""
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
JOINED = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
OUT = os.path.join(_HERE, "course_geometry.csv")

FIELDS = ["course", "handedness", "course_shape", "circumference_f", "run_in_y",
          "course_character", "undulation", "uphill_finish",
          "course_character_verified", "undulation_verified", "uphill_finish_verified",
          "notes"]

# PER-FIELD, PER-COURSE Tier-2 verification. Tier-2 fields start unverified; a
# human confirms values course-by-course and the relevant <field>_verified flips
# to true. course_character / undulation: not verified anywhere yet. uphill_finish:
# verified for the courses below (the defining stiff-uphill finishes and the clear
# flat/downhill finishes), checked against well-established track facts.
VERIFIED_UPHILL = {
    # stiff uphill finishes (uphill_finish = Yes)
    "Sandown", "Towcester", "Ascot", "Pontefract", "Chepstow", "Hereford", "Fakenham",
    # flat / downhill finishes (uphill_finish = No)
    "Epsom", "Goodwood", "Newbury", "Uttoxeter",
}

# course: (handedness, shape, circ_f, run_in_y,            # TIER 1
#          character, undulation, uphill_finish,           # TIER 2 (proposed)
#          notes)
# run_in_y left "" where not confidently known (no guessing).
GEOMETRY = {
    "Aintree":          ("Left", "Triangular", 12, "260", "Galloping", "Flat", "No",
                         "Mildmay course shown; Grand National course ~18f, run-in 494y"),
    "Ascot":            ("Right", "Triangular", 14, "", "Galloping", "Undulating", "Yes",
                         "Round course rises to the line"),
    "Ayr":              ("Left", "Oval", 12, "", "Galloping", "Flat", "No", ""),
    "Bangor-on-Dee":    ("Left", "Oval", 9, "", "Sharp", "Flat", "No", "No grandstand bend; flat sharp circuit"),
    "Bath":             ("Left", "Oval", 12, "", "Galloping", "Undulating", "Yes",
                         "Highest course in GB; stiff uphill run-in"),
    "Beverley":         ("Right", "Oval", 11, "", "Stiff", "Undulating", "Yes", "Stiff uphill last 3f"),
    "Brighton":         ("Left", "Horseshoe", 12, "", "Sharp", "Undulating", "No", "Switchback, Epsom-like"),
    "Carlisle":         ("Right", "Pear", 13, "", "Stiff", "Undulating", "Yes", "Stiff uphill finish"),
    "Cartmel":          ("Left", "Oval", 8, "880", "Sharp", "Undulating", "No",
                         "Longest run-in in GB (~4f)"),
    "Catterick":        ("Left", "Oval", 10, "", "Sharp", "Undulating", "No", ""),
    "Chelmsford (AW)":  ("Left", "Oval", 10, "", "Galloping", "Flat", "No", "Polytrack; wide sweeping turns"),
    "Cheltenham":       ("Left", "Oval", 12, "", "Galloping", "Undulating", "Yes",
                         "Old course ~12f / New ~13f; famous uphill finish"),
    "Chepstow":         ("Left", "Oval", 16, "", "Galloping", "Undulating", "Yes", ""),
    "Chester":          ("Left", "Round", 8, "", "Sharp", "Flat", "No",
                         "Smallest, near-circular, tightest turning track in GB"),
    "Doncaster":        ("Left", "Pear", 16, "", "Galloping", "Flat", "No", "Plus straight mile"),
    "Epsom":            ("Left", "Horseshoe", 12, "", "Galloping", "Undulating", "No",
                         "Severe camber/descent to Tattenham; ~flat finish"),
    "Exeter":           ("Right", "Oval", 16, "", "Stiff", "Undulating", "Yes", "One of the stiffest tracks"),
    "Fakenham":         ("Left", "Oval", 8, "", "Sharp", "Undulating", "Yes", "Tight square-ish circuit"),
    "Ffos Las":         ("Left", "Oval", 12, "", "Galloping", "Flat", "No", "Newest GB course (2009)"),
    "Fontwell":         ("Figure-of-eight", "Figure-of-eight", 10, "", "Sharp", "Undulating", "No",
                         "Chase course is figure-of-eight; hurdles a left-handed oval"),
    "Goodwood":         ("Right", "Horseshoe", 14, "", "Galloping", "Undulating", "No",
                         "Loop/horseshoe with downhill sections"),
    "Hamilton":         ("Right", "Oval", 13, "", "Galloping", "Undulating", "Yes",
                         "Rises to the line; straight 6f"),
    "Haydock":          ("Left", "Oval", 13, "", "Galloping", "Flat", "No", ""),
    "Hereford":         ("Right", "Oval", 12, "", "Galloping", "Undulating", "Yes", "Square-ish circuit"),
    "Hexham":           ("Left", "Oval", 12, "", "Stiff", "Undulating", "Yes", "Very undulating, stiff finish"),
    "Huntingdon":       ("Right", "Oval", 12, "", "Galloping", "Flat", "No", ""),
    "Kelso":            ("Left", "Oval", 13, "", "Galloping", "Undulating", "Yes", "Stiff uphill run-in"),
    "Kempton":          ("Right", "Triangular", 13, "", "Galloping", "Flat", "No", "Jumps (turf) course"),
    "Kempton (AW)":     ("Right", "Oval", 10, "", "Sharp", "Flat", "No", "Polytrack; inner & outer ovals"),
    "Leicester":        ("Right", "Oval", 14, "", "Galloping", "Undulating", "Yes", "Stiff finish"),
    "Lingfield":        ("Left", "Horseshoe", 12, "", "Sharp", "Undulating", "No", "Turf course (switchback)"),
    "Lingfield (AW)":   ("Left", "Oval", 10, "", "Sharp", "Flat", "No", "Polytrack"),
    "Ludlow":           ("Right", "Oval", 12, "", "Galloping", "Flat", "No", ""),
    "Market Rasen":     ("Right", "Oval", 10, "", "Sharp", "Undulating", "No", ""),
    "Musselburgh":      ("Right", "Oval", 10, "", "Sharp", "Flat", "No", ""),
    "Newbury":          ("Left", "Oval", 14, "", "Galloping", "Flat", "No", "Fair galloping test"),
    "Newcastle":        ("Left", "Oval", 14, "", "Galloping", "Undulating", "Yes", "Turf (jumps); uphill finish"),
    "Newcastle (AW)":   ("Left", "Oval", 14, "", "Galloping", "Flat", "No", "Tapeta; straight mile + round"),
    "Newmarket":        ("Right", "Oval", 18, "", "Galloping", "Undulating", "Yes",
                         "Rowley Mile; broad galloping straights, The Dip then rise to line"),
    "Newmarket (July)": ("Right", "Oval", 16, "", "Galloping", "Undulating", "Yes",
                         "July course; dip and rise to the line"),
    "Newton Abbot":     ("Left", "Oval", 9, "", "Sharp", "Flat", "No", "Very sharp"),
    "Nottingham":       ("Left", "Oval", 12, "", "Galloping", "Flat", "No", ""),
    "Perth":            ("Right", "Oval", 10, "", "Galloping", "Flat", "No", ""),
    "Plumpton":         ("Left", "Oval", 9, "", "Sharp", "Undulating", "Yes", "Tight, stiff uphill finish"),
    "Pontefract":       ("Left", "Oval", 16, "", "Galloping", "Undulating", "Yes",
                         "Undulating, stiff uphill finish (one of the stiffest)"),
    "Redcar":           ("Left", "Oval", 14, "", "Galloping", "Flat", "No", ""),
    "Ripon":            ("Right", "Oval", 13, "", "Sharp", "Undulating", "No", ""),
    "Salisbury":        ("Right", "Oval", 12, "", "Galloping", "Undulating", "Yes",
                         "Straight mile + loop; stiff last half-mile"),
    "Sandown":          ("Right", "Oval", 13, "", "Galloping", "Undulating", "Yes",
                         "Famous uphill finish; separate uphill straight 5f"),
    "Sedgefield":       ("Left", "Oval", 10, "", "Sharp", "Undulating", "No", ""),
    "Southwell":        ("Left", "Oval", 10, "", "Sharp", "Flat", "No", "Turf course"),
    "Southwell (AW)":   ("Left", "Oval", 10, "", "Sharp", "Flat", "No", "Fibresand/Tapeta; tight"),
    "Stratford":        ("Left", "Oval", 10, "", "Sharp", "Flat", "No", ""),
    "Taunton":          ("Right", "Oval", 12, "", "Galloping", "Flat", "No", ""),
    "Thirsk":           ("Left", "Oval", 10, "", "Sharp", "Flat", "No", ""),
    "Towcester":        ("Right", "Oval", 14, "", "Stiff", "Undulating", "Yes",
                         "One of the stiffest uphill finishes; very few rows in data"),
    "Uttoxeter":        ("Left", "Oval", 12, "", "Galloping", "Undulating", "No", ""),
    "Warwick":          ("Left", "Oval", 13, "", "Sharp", "Undulating", "No", "Sharp bends"),
    "Wetherby":         ("Left", "Oval", 14, "", "Galloping", "Flat", "No", ""),
    "Wincanton":        ("Right", "Oval", 13, "", "Galloping", "Flat", "No", ""),
    "Windsor":          ("Figure-of-eight", "Figure-of-eight", 12, "", "Galloping", "Flat", "No",
                         "Figure-of-eight"),
    "Wolverhampton (AW)": ("Left", "Oval", 9, "", "Sharp", "Flat", "No", "Tapeta; tight"),
    "Worcester":        ("Left", "Oval", 13, "", "Galloping", "Flat", "No", ""),
    "Yarmouth":         ("Left", "Oval", 13, "", "Galloping", "Flat", "No", ""),
    "York":             ("Left", "Horseshoe", 16, "", "Galloping", "Flat", "No", "Galloping, flat ~2m"),
}


def distinct_courses(path):
    seen = set()
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            seen.add(r["course"])
    return seen


def main():
    data_courses = distinct_courses(JOINED)
    table_courses = set(GEOMETRY)

    missing = sorted(data_courses - table_courses)   # in data, no geometry -> would join to blank
    extra = sorted(table_courses - data_courses)      # in table, not in data -> name typo

    if missing:
        print("FLAG -- courses in the dataset with NO geometry row (fix before writing):")
        for c in missing:
            print(f"   |{c}|")
    if extra:
        print("FLAG -- geometry rows whose name does NOT byte-match any dataset course:")
        for c in extra:
            print(f"   |{c}|")
    if missing or extra:
        print(f"\nABORT: {len(missing)} missing, {len(extra)} unmatched. No file written.")
        sys.exit(1)

    with open(OUT, "w", newline="") as g:
        w = csv.DictWriter(g, fieldnames=FIELDS)
        w.writeheader()
        for course in sorted(GEOMETRY):
            hand, shape, circ, runin, char, und, up, notes = GEOMETRY[course]
            w.writerow({
                "course": course, "handedness": hand, "course_shape": shape,
                "circumference_f": circ, "run_in_y": runin,
                "course_character": char, "undulation": und, "uphill_finish": up,
                "course_character_verified": "false",
                "undulation_verified": "false",
                "uphill_finish_verified": "true" if course in VERIFIED_UPHILL else "false",
                "notes": notes,
            })
    print(f"OK -- {len(GEOMETRY)}/{len(data_courses)} dataset courses matched, "
          f"0 missing, 0 unmatched.")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
