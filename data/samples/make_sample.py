"""
Generate a synthetic Betfair Historical stream file (newline-delimited JSON).

The structure mirrors a real Betfair "Stream" historical file:
 - each line is one market-change message (op="mcm")
 - the first relevant packet carries a full marketDefinition (img=true)
 - runners accumulate traded volume in the "rc" (runner change) arrays
 - at the off, the market goes in-play; the SP reconciliation populates
   each runner's "bsp" field in the marketDefinition.

This lets us write + test the TAR->BSP parser before buying any real data.
Drop a real .bz2/.tar ADVANCED file into data/historical/ and the same
parser logic applies.
"""
import json, bz2, os

MARKET_ID = "1.234567890"
RUNNERS = [
    # selection_id, name, final BSP
    (47001, "Front Runner",   3.85),
    (47002, "Clean Benchmark", 5.40),
    (47003, "Closing Line",    7.20),
    (47004, "Longshot Lad",   28.00),
    (47005, "Even Money Fav",  2.10),
]

def runner_def(sel, status="ACTIVE", bsp=None):
    d = {"id": sel, "status": status, "sortPriority": 1}
    if bsp is not None:
        d["bsp"] = bsp
    return d

def market_def(in_play=False, with_bsp=False):
    return {
        "betDelay": 0,
        "bspReconciled": with_bsp,
        "complete": True,
        "inPlay": in_play,
        "numberOfWinners": 1,
        "marketType": "WIN",
        "countryCode": "GB",
        "bspMarket": True,
        "eventTypeId": "7",            # 7 = horse racing
        "venue": "Ascot",
        "marketTime": "2025-06-21T14:30:00.000Z",
        "status": "OPEN" if not in_play else "SUSPENDED",
        "runners": [
            runner_def(sid, bsp=(bsp if with_bsp else None))
            for sid, _, bsp in RUNNERS
        ],
    }

lines = []

# 1) Opening image packet (full market definition, no BSP yet)
lines.append({"op": "mcm", "clk": "1", "pt": 1750000000000,
    "mc": [{"id": MARKET_ID, "img": True,
            "marketDefinition": market_def(in_play=False, with_bsp=False),
            "rc": [{"id": sid, "ltp": bsp * 1.10, "tv": 50.0}
                   for sid, _, bsp in RUNNERS]}]})

# 2) A few pre-off price moves (volume building, prices drifting toward BSP)
for step, pt in enumerate([1750000300000, 1750000600000, 1750000800000]):
    lines.append({"op": "mcm", "clk": str(step + 2), "pt": pt,
        "mc": [{"id": MARKET_ID,
                "rc": [{"id": sid, "ltp": round(bsp * (1.06 - 0.02 * step), 2),
                        "tv": 50.0 + 120.0 * (step + 1)}
                       for sid, _, bsp in RUNNERS]}]})

# 3) The off: market suspends and SP reconciles -> BSP now present
lines.append({"op": "mcm", "clk": "5", "pt": 1750000810000,
    "mc": [{"id": MARKET_ID,
            "marketDefinition": market_def(in_play=True, with_bsp=True)}]})

out_dir = os.path.dirname(__file__)
raw_path = os.path.join(out_dir, "sample_market_1.234567890.jsonl")
with open(raw_path, "w") as f:
    for ln in lines:
        f.write(json.dumps(ln) + "\n")

# Also write a .bz2 version, since real Historical files are bz2 inside a TAR
with bz2.open(raw_path + ".bz2", "wt") as f:
    for ln in lines:
        f.write(json.dumps(ln) + "\n")

print(f"Wrote {len(lines)} packets to:")
print(" ", raw_path)
print(" ", raw_path + ".bz2")
