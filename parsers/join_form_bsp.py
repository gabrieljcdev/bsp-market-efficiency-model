"""
join_form_bsp.py  --  join Racing Post form (Block 3) to Betfair BSP (Block 2).

The two sources share no clean key, so we join on race + horse:
  * race key  = (date, normalised course)   -- a horse runs at most once per
                course per day, so date+course+horse is effectively unique.
  * runner    = normalised horse name (strip leading cloth numbers, country
                suffixes, punctuation; collapse spaces; uppercase).

Off-times are carried from both sides as a *validation* signal, not a hard key:
Betfair market_time is UTC, RP off is UK local. September 2025 is entirely BST
(UTC+1), so the expected relation is  RP_off == Betfair_utc + 1h. We report how
often that holds on matched runners to confirm the race alignment is right.

Output (data/joined/):
  joined_gb_2025_09.csv   -- one row per runner: form features AND its BSP
  unmatched_form.csv      -- RP runners with no BSP match (inspect name quirks)
  unmatched_bsp.csv       -- BSP runners no RP row matched

BSP here is the scoring benchmark that travels with each runner; downstream
feature tables must still exclude it.
"""
import os, csv, re
from datetime import datetime, timedelta
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BSP_CSV = os.path.join(_ROOT, "output", "bsp_table.csv")
FORM_CSV = os.path.join(_ROOT, "data", "form", "rp_form_gb_2025_09.csv")
OUT_DIR = os.path.join(_ROOT, "data", "joined")

# Betfair venue -> canonical, where plain (AW)-stripping isn't enough.
COURSE_ALIASES = {
    "chelmsford city": "chelmsford",
}

_CLOTH = re.compile(r"^\s*\d+\s*[.)]?\s*")          # leading "1. " / "1) " / "1 "
_COUNTRY = re.compile(r"\s*\([A-Z]{1,3}\d?\)\s*$")  # trailing "(IRE)" / "(USA2)"
_NONALNUM = re.compile(r"[^A-Z0-9 ]+")
_PAREN = re.compile(r"\([^)]*\)")                   # any "(...)" in a course name
_WS = re.compile(r"\s+")


def norm_name(raw):
    """Normalise a horse name for cross-source matching."""
    if raw is None:
        return ""
    s = raw.strip()
    s = _CLOTH.sub("", s)                 # strip Betfair leading cloth number
    s = s.upper()
    s = _COUNTRY.sub("", s)               # strip country suffix
    s = _NONALNUM.sub(" ", s)             # drop apostrophes/hyphens/dots
    s = _WS.sub(" ", s).strip()
    return s


def norm_course(raw):
    """Normalise a course name (drop (AW) etc.; apply alias table)."""
    if raw is None:
        return ""
    s = _PAREN.sub("", raw).lower()
    s = _WS.sub(" ", s).strip()
    return COURSE_ALIASES.get(s, s)


def bsp_local_dt(market_time):
    """Betfair marketTime (UTC ISO) -> UK-local datetime (BST = UTC+1 in Sept)."""
    if not market_time:
        return None
    s = market_time.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s) + timedelta(hours=1)
    except ValueError:
        return None


def load_bsp():
    """GB WIN runners that ran (WINNER/LOSER), keyed by (date, course, name)."""
    by_key = {}
    collisions = 0
    total = 0
    with open(BSP_CSV, newline="") as f:
        for r in csv.DictReader(f):
            if r["country"] != "GB" or r["market_type"] != "WIN":
                continue
            if r["runner_status"] not in ("WINNER", "LOSER"):
                continue
            dt = bsp_local_dt(r["market_time"])
            if dt is None:
                continue
            total += 1
            key = (dt.date().isoformat(), norm_course(r["venue"]),
                   norm_name(r.get("name") or ""))
            row = {
                "bsp": r["bsp"], "last_preoff_ltp": r["last_preoff_ltp"],
                "total_volume": r["total_volume"], "market_id": r["market_id"],
                "selection_id": r["selection_id"],
                "bf_off": dt.strftime("%H:%M"), "bf_venue": r["venue"],
                "bf_name_raw": r.get("name"), "runner_status": r["runner_status"],
                "_matched": False,
            }
            if key in by_key:
                collisions += 1
            by_key[key] = row
    return by_key, total, collisions


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bsp, bsp_total, bsp_collisions = load_bsp()
    print(f"BSP GB-WIN runners (ran): {bsp_total}  | unique keys: {len(bsp)}"
          f"  | key collisions: {bsp_collisions}")

    with open(FORM_CSV, newline="") as f:
        form_rows = list(csv.DictReader(f))
        form_cols = form_rows[0].keys() if form_rows else []
    print(f"RP form runners: {len(form_rows)}")

    joined, unmatched_form = [], []
    off_agree = off_total = 0
    for r in form_rows:
        key = (r["date"], norm_course(r["course"]), norm_name(r["horse"]))
        hit = bsp.get(key)
        if not hit:
            unmatched_form.append(r)
            continue
        hit["_matched"] = True
        # off-time validation (RP local off vs Betfair UTC+1)
        if r.get("off") and hit["bf_off"]:
            off_total += 1
            off_agree += int(r["off"] == hit["bf_off"])
        out = dict(r)
        out["norm_horse"] = norm_name(r["horse"])
        out["norm_course"] = norm_course(r["course"])
        out["bf_off"] = hit["bf_off"]
        out["bsp"] = hit["bsp"]
        out["bf_last_preoff_ltp"] = hit["last_preoff_ltp"]
        out["bf_total_volume"] = hit["total_volume"]
        out["bf_market_id"] = hit["market_id"]
        out["bf_selection_id"] = hit["selection_id"]
        out["bf_runner_status"] = hit["runner_status"]
        out["bf_name_raw"] = hit["bf_name_raw"]
        joined.append(out)

    unmatched_bsp = [v for v in bsp.values() if not v["_matched"]]

    # ---- write outputs ------------------------------------------------------
    join_path = os.path.join(OUT_DIR, "joined_gb_2025_09.csv")
    out_cols = list(form_cols) + ["norm_horse", "norm_course", "bf_off", "bsp",
                                  "bf_last_preoff_ltp", "bf_total_volume",
                                  "bf_market_id", "bf_selection_id",
                                  "bf_runner_status", "bf_name_raw"]
    with open(join_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(joined)

    uf_path = os.path.join(OUT_DIR, "unmatched_form.csv")
    with open(uf_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(form_cols), extrasaction="ignore")
        w.writeheader()
        w.writerows(unmatched_form)

    ub_path = os.path.join(OUT_DIR, "unmatched_bsp.csv")
    with open(ub_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(unmatched_bsp[0].keys())
                           if unmatched_bsp else ["bf_name_raw"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(unmatched_bsp)

    # ---- report -------------------------------------------------------------
    n_form = len(form_rows)
    print("\n=== JOIN REPORT ====================================")
    print(f"joined rows                 : {len(joined)}")
    print(f"match rate (form -> BSP)    : {len(joined)}/{n_form} "
          f"({100*len(joined)/n_form:.1f}%)")
    print(f"match rate (BSP -> form)    : {len(joined)}/{len(bsp)} "
          f"({100*len(joined)/len(bsp):.1f}%)")
    print(f"unmatched form runners      : {len(unmatched_form)}")
    print(f"unmatched BSP runners       : {len(unmatched_bsp)}")
    if off_total:
        print(f"off-time agreement (matched): {off_agree}/{off_total} "
              f"({100*off_agree/off_total:.1f}%)  [RP off == BF utc+1h]")

    print("\n--- 5 sample JOINED rows (date course horse | pos rpr | bsp) ---")
    for r in joined[:5]:
        print(f"  {r['date']} {r['course']:<14} {r['horse']:<22} "
              f"pos={r['pos']:<3} rpr={r['or'] and r['rpr']:<4} bsp={r['bsp']}")

    print("\n--- 5 unmatched FORM rows (date course horse) ---")
    for r in unmatched_form[:5]:
        print(f"  {r['date']} {r['course']:<16} {r['horse']!r}")

    print("\n--- 5 unmatched BSP rows (date off venue name) ---")
    for r in unmatched_bsp[:5]:
        print(f"  {r['bf_venue']:<14} {r['bf_off']} {r['bf_name_raw']!r}")

    print(f"\nwrote: {join_path}")
    print(f"       {uf_path}")
    print(f"       {ub_path}")


if __name__ == "__main__":
    main()
