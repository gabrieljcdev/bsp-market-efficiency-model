#!/usr/bin/env python3
"""build_weather.py -- Block 4 (reduced, visibility-only probe).

Merges the fetched per-race weather (data/weather/weather_by_race.csv) onto the
base joined table and writes joined_gb_2018_2026_wx.csv with the columns the
weather scorer needs, plus a small set of leakage-safe derived features.

CONTEXT (see PROJECT_NOTES + the Block-4 fog gate): true fog (<1km) occurs in
only 4 (val) / 7 (holdout) races over 2022-2026 -> far too rare to test. So the
race-level fog flag is under-powered. The ONE identifiable, powered test left is
a within-race INTERACTION: does lower visibility change the draw advantage? A
race-CONSTANT fog flag cancels in a conditional logit; visibility x draw does not.

FEATURES (all pre-race: visibility at the off-hour is an environmental condition,
not an outcome -> no leakage; the anchor test in the scorer confirms it):
  wx_visibility            metres at nearest hour to the off (race-level)
  wx_temp_dewpoint_spread  temp - dewpoint (small spread => fog-prone; cross-check)
  wx_wind_speed            10 m wind (disperses fog)
  draw_norm                draw mapped to [0,1] within race (flat/AW only)
  neg_log_vis              -ln(visibility) : higher => foggier (raw; scorer z's it)
The visibility x draw interaction itself is built in the scorer after z-scoring.

Output is gitignored (regenerable).
"""
import csv
import math
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
WX = os.path.join(_ROOT, "data", "weather", "weather_by_race.csv")
OUT = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_wx.csv")

CARRY = ["date", "course", "off", "type", "surface", "class", "ran",
         "or", "draw", "lbs", "age", "pos", "bsp", "wap"]
WX_OUT = ["wx_in_window", "wx_visibility", "wx_temp_dewpoint_spread",
          "wx_wind_speed", "draw_norm", "neg_log_vis"]


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    # 1. index weather by (date, course, off)
    wx = {}
    with open(WX, newline="") as f:
        for r in csv.DictReader(f):
            key = (r["date"], r["course"], r["off"])
            wx[key] = r

    # 2. first pass: per-race draw min/max for within-race normalisation
    draw_lo, draw_hi = {}, {}
    with open(BASE, newline="") as f:
        for r in csv.DictReader(f):
            d = fnum(r.get("draw"))
            if d is None or d <= 0:
                continue
            rid = (r["date"], r["course"], r["off"])
            draw_lo[rid] = min(draw_lo.get(rid, d), d)
            draw_hi[rid] = max(draw_hi.get(rid, d), d)

    # 3. second pass: write merged rows
    n = n_window = n_vis = 0
    with open(BASE, newline="") as f, open(OUT, "w", newline="") as g:
        rd = csv.DictReader(f)
        w = csv.writer(g)
        w.writerow(CARRY + WX_OUT)
        for r in rd:
            n += 1
            rid = (r["date"], r["course"], r["off"])
            wr = wx.get(rid, {})
            in_window = wr.get("wx_in_window", "0")
            vis = fnum(wr.get("wx_visibility"))
            temp = fnum(wr.get("wx_temperature_2m"))
            dew = fnum(wr.get("wx_dew_point_2m"))
            wind = fnum(wr.get("wx_wind_speed_10m"))

            spread = (temp - dew) if (temp is not None and dew is not None) else ""
            neg_log_vis = (-math.log(vis)) if (vis is not None and vis > 0) else ""

            # within-race draw normalisation (flat/AW only); else blank
            d = fnum(r.get("draw"))
            draw_norm = ""
            if d is not None and d > 0 and rid in draw_lo:
                lo, hi = draw_lo[rid], draw_hi[rid]
                draw_norm = ((d - lo) / (hi - lo)) if hi > lo else 0.5

            if in_window == "1":
                n_window += 1
            if vis is not None:
                n_vis += 1

            carry_vals = [r.get(c, "") for c in CARRY]
            wx_vals = [in_window,
                       vis if vis is not None else "",
                       spread,
                       wind if wind is not None else "",
                       draw_norm,
                       neg_log_vis]
            w.writerow(carry_vals + wx_vals)

    print(f"wrote {OUT}")
    print(f"  rows                : {n}")
    print(f"  in covered window   : {n_window}")
    print(f"  with visibility     : {n_vis}")


if __name__ == "__main__":
    main()
