"""GB racecourse -> (lat, lon) lookup for weather acquisition (visibility-only probe).

Built from scratch 2026-06-29 (Block 1): the joined dataset holds 65 distinct
course strings (cut -f3 joined_gb_2018_2026.csv). The (AW)/(July) suffixed
strings are the *same physical site* as their turf/Rowley counterparts and share
an ERA5 grid cell, so they map to the same coordinates.

Coordinates are the racecourse grandstand/enclosure to ~3 d.p. (≈100 m), far
finer than the ERA5 reanalysis grid (~9-31 km), so sub-km precision is moot — the
only thing that matters is selecting the right grid cell.

Usage:
    from course_coords import lookup, COORDS, normalise
    lat, lon = lookup("Newmarket (July)")   # -> (52.235, 0.39)
"""

# Keyed by the EXACT course string as it appears in joined_gb_2018_2026.csv
# (so an unmapped string is an explicit KeyError, never a silent wrong cell).
# (AW) and (July) variants intentionally repeat the base site's coordinates.
COORDS = {
    # --- All-weather sites (share coords with their turf namesake where one exists) ---
    "Wolverhampton (AW)": (52.5912, -2.1490),
    "Kempton (AW)":       (51.4186, -0.4078),
    "Kempton":            (51.4186, -0.4078),
    "Newcastle (AW)":     (55.0103, -1.6055),
    "Newcastle":          (55.0103, -1.6055),
    "Lingfield (AW)":     (51.1700, -0.0140),
    "Lingfield":          (51.1700, -0.0140),
    "Southwell (AW)":     (53.0820, -0.9530),
    "Southwell":          (53.0820, -0.9530),
    "Chelmsford (AW)":    (51.7560,  0.4380),
    # --- Newmarket: Rowley Mile and July course ~1 km apart, same grid cell ---
    "Newmarket":          (52.2370,  0.3830),
    "Newmarket (July)":   (52.2370,  0.3830),
    # --- Turf / jumps ---
    "Doncaster":          (53.5180, -1.1140),
    "Newbury":            (51.3990, -1.3010),
    "Ayr":                (55.4570, -4.6320),
    "Ascot":              (51.4100, -0.6800),
    "Chepstow":           (51.6420, -2.6790),
    "Haydock":            (53.4790, -2.6300),
    "Windsor":            (51.4900, -0.6160),
    "Catterick":          (54.3760, -1.6320),
    "York":               (53.9430, -1.0930),
    "Uttoxeter":          (52.8990, -1.8650),
    "Musselburgh":        (55.9430, -3.0480),
    "Leicester":          (52.6010, -1.0840),
    "Carlisle":           (54.8730, -2.9270),
    "Yarmouth":           (52.6020,  1.7160),
    "Sandown":            (51.3650, -0.3590),
    "Nottingham":         (52.9510, -1.0930),
    "Redcar":             (54.6160, -1.0680),
    "Bath":               (51.4180, -2.4080),
    "Cheltenham":         (51.9250, -2.0580),
    "Thirsk":             (54.2330, -1.3590),
    "Beverley":           (53.8460, -0.4490),
    "Goodwood":           (50.8980, -0.7430),
    "Ffos Las":           (51.7290, -4.2540),
    "Market Rasen":       (53.3870, -0.3210),
    "Worcester":          (52.1960, -2.2300),
    "Warwick":            (52.2760, -1.5950),
    "Wetherby":           (53.9370, -1.3830),
    "Huntingdon":         (52.3530, -0.1660),
    "Hamilton":           (55.7840, -4.0490),
    "Brighton":           (50.8330, -0.0900),
    "Ripon":              (54.1330, -1.5040),
    "Pontefract":         (53.6940, -1.3160),
    "Wincanton":          (51.0590, -2.4070),
    "Exeter":             (50.6580, -3.4760),
    "Stratford":          (52.1880, -1.7180),
    "Sedgefield":         (54.6500, -1.4490),
    "Hexham":             (54.9650, -2.1230),
    "Chester":            (53.1880, -2.8970),
    "Salisbury":          (51.0560, -1.8390),
    "Newton Abbot":       (50.5340, -3.5940),
    "Taunton":            (51.0060, -3.1330),
    "Perth":              (56.4310, -3.3960),
    "Ludlow":             (52.3840, -2.7510),
    "Hereford":           (52.0670, -2.7320),
    "Kelso":              (55.6010, -2.4290),
    "Plumpton":           (50.9230, -0.0470),
    "Bangor-on-Dee":      (52.9930, -2.9170),
    "Aintree":            (53.4760, -2.9420),
    "Epsom":              (51.3120, -0.2550),
    "Cartmel":            (54.2000, -2.9520),
    "Fontwell":           (50.8530, -0.6520),
    "Fakenham":           (52.8240,  0.8470),
    "Towcester":          (52.1230, -0.9920),
}


def normalise(course: str) -> str:
    """Strip surrounding whitespace; leave the (AW)/(July) suffix intact since
    those are distinct keys. Defensive only — exact strings are preferred."""
    return (course or "").strip()


def lookup(course: str):
    """Return (lat, lon) for a course string, or raise KeyError. Try the exact
    string, then a whitespace-normalised form."""
    key = normalise(course)
    if key in COORDS:
        return COORDS[key]
    raise KeyError(f"No coordinates for course {course!r}")


if __name__ == "__main__":
    print(f"{len(COORDS)} course strings mapped; "
          f"{len(set(COORDS.values()))} distinct physical sites")
