"""
parse_bsp.py  --  Betfair Historical stream file  ->  BSP table.

First vertical slice of the pipeline. Reads a Betfair "Stream" historical
file (newline-delimited JSON, plain or .bz2) and extracts, per runner:
    market_id, selection_id, venue, market_time, country, status,
    bsp (reconciled starting price), last_preoff_ltp, total_volume.

The BSP column is the closing-line benchmark every selection gets scored
against. last_preoff_ltp is a stand-in for "the price you could have struck"
until we wire in real bet timestamps -- CLV = struck / bsp - 1.

Works on the synthetic sample now; the identical logic applies to a real
Betfair ADVANCED file (which is bz2 stream files bundled inside a .tar).
For a real .tar, iterate its members and feed each to parse_stream().
"""
import json, bz2, io, os, csv, sys, glob, tarfile


def _open(path):
    if path.endswith(".bz2"):
        return bz2.open(path, "rt")
    return open(path, "rt")


def accumulate_stream(fileobj, market_meta, runners):
    """
    Consume a newline-delimited mcm stream, accumulating into the caller's
    market_meta and runners dicts. Keying runners by (market_id, sel_id)
    makes this idempotent across files that describe the same market (the
    Betfair BASIC archive stores each market both under <eventId>.bz2 and
    1.<marketId>.bz2 -- feeding both just re-updates the same rows).
    Does NOT fold meta onto rows; call fold_meta() once at the end.
    """
    inplay = {}               # market_id -> bool (has the off happened yet?)

    for raw in fileobj:
        raw = raw.strip()
        if not raw:
            continue
        msg = json.loads(raw)
        if msg.get("op") != "mcm":
            continue
        for mc in msg.get("mc", []):
            mid = mc["id"]

            # ---- market definition packet (static fields + BSP at the off)
            mdef = mc.get("marketDefinition")
            if mdef:
                inplay[mid] = bool(mdef.get("inPlay", False))
                market_meta[mid] = {
                    "venue": mdef.get("venue"),
                    "market_time": mdef.get("marketTime"),
                    "country": mdef.get("countryCode"),
                    "market_type": mdef.get("marketType"),
                    "event_type": mdef.get("eventTypeId"),
                    "status": mdef.get("status"),
                    "bsp_reconciled": mdef.get("bspReconciled", False),
                }
                for r in mdef.get("runners", []):
                    key = (mid, r["id"])
                    row = runners.setdefault(key, _blank_row(mid, r["id"]))
                    row["runner_status"] = r.get("status")
                    if r.get("name") is not None:
                        row["name"] = r["name"]
                    if r.get("bsp") is not None:
                        row["bsp"] = r["bsp"]

            # ---- runner change packet (prices + traded volume)
            # Only keep the last PRE-OFF traded price: once the market turns
            # in-play, ltp races to ~1.0 (winner) / ~1000 (loser) and is
            # useless as a struck-price stand-in.
            for rc in mc.get("rc", []):
                key = (mid, rc["id"])
                row = runners.setdefault(key, _blank_row(mid, rc["id"]))
                if rc.get("ltp") is not None and not inplay.get(mid, False):
                    row["last_preoff_ltp"] = rc["ltp"]
                if rc.get("tv") is not None:
                    row["total_volume"] = rc["tv"]

    return market_meta, runners


def fold_meta(market_meta, runners):
    """Fold static market fields onto every runner row (in place)."""
    for (mid, _sid), row in runners.items():
        row.update({f"market_{k}" if k in ("status",) else k: v
                    for k, v in market_meta.get(mid, {}).items()})
    return runners


def parse_stream(fileobj):
    """Single-stream convenience wrapper: returns folded runners dict.
    Preserves the original parse_stream() contract for callers/tests."""
    market_meta, runners = {}, {}
    accumulate_stream(fileobj, market_meta, runners)
    return fold_meta(market_meta, runners)


def _iter_members(path):
    """Yield (member_name, text_fileobj) for every stream in `path`.
    Handles a .tar / .tar.bz2 / .tgz archive (iterating its members,
    decompressing .bz2 members on the fly) or a single .bz2 / plain file.
    """
    if path.endswith((".tar", ".tar.bz2", ".tbz2", ".tgz", ".tar.gz")):
        with tarfile.open(path, "r:*") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                f = tf.extractfile(m)
                if f is None:
                    continue
                data = f.read()
                if m.name.endswith(".bz2"):
                    data = bz2.decompress(data)
                yield m.name, io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
    else:
        with _open(path) as f:
            yield os.path.basename(path), f


def parse_paths(paths, event_type_filter=7):
    """Accumulate every stream under `paths` (files, archives, or dirs) into
    one runners table. Filters to markets whose eventTypeId == event_type_filter
    (horse racing == 7); pass None to keep all. Returns (rows, stats)."""
    market_meta, runners = {}, {}
    files = 0
    for path in paths:
        for name, fobj in _iter_members(path):
            files += 1
            accumulate_stream(fobj, market_meta, runners)
    fold_meta(market_meta, runners)

    # marketType distribution (post event-type filter) for reporting
    from collections import Counter
    mkt_types = Counter()
    rows = []
    for row in runners.values():
        et = row.get("event_type")
        if event_type_filter is not None and str(et) != str(event_type_filter):
            continue
        mkt_types[row.get("market_type")] += 1
        rows.append(row)
    rows.sort(key=lambda r: (str(r["market_id"]), r["selection_id"]))
    stats = {
        "files": files,
        "markets_total": len({k[0] for k in runners}),
        "runner_rows_kept": len(rows),
        "markets_kept": len({r["market_id"] for r in rows}),
        "market_types": dict(mkt_types),
    }
    return rows, stats


def _blank_row(mid, sid):
    return {
        "market_id": mid, "selection_id": sid, "name": None,
        "bsp": None, "last_preoff_ltp": None, "total_volume": None,
        "runner_status": None,
    }


def to_table(runners):
    rows = sorted(runners.values(),
                  key=lambda r: (r["market_id"], r["selection_id"]))
    return rows


def write_csv(rows, out_path):
    if not rows:
        print("No rows parsed.")
        return
    cols = ["market_id", "selection_id", "name", "venue", "market_time",
            "country", "event_type", "market_type", "runner_status", "bsp",
            "last_preoff_ltp", "total_volume", "bsp_reconciled"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} runner rows -> {out_path}")


def parse_file(path):
    with _open(path) as f:
        return to_table(parse_stream(f))


def _expand(arg, root):
    """Turn a CLI arg into a list of concrete file paths. A directory expands
    to every stream/archive inside it; a file is used as-is."""
    if os.path.isdir(arg):
        out = []
        for pat in ("*.tar", "*.tar.bz2", "*.tbz2", "*.tgz", "*.tar.gz",
                    "*.bz2", "*.jsonl"):
            out += glob.glob(os.path.join(arg, "**", pat), recursive=True)
        return sorted(out)
    return [arg]


if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    arg = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(_root, "data/historical")
    paths = _expand(arg, _root)
    print(f"Reading {len(paths)} path(s) from {arg} ...")
    rows, stats = parse_paths(paths, event_type_filter=7)

    print("\n--- parse summary -------------------------------------------")
    print(f"stream files read : {stats['files']}")
    print(f"markets seen       : {stats['markets_total']}")
    print(f"markets kept (et=7): {stats['markets_kept']}")
    print(f"runner rows kept   : {stats['runner_rows_kept']}")
    print(f"market_type counts : {stats['market_types']}")

    out_dir = os.path.join(_root, "output")
    os.makedirs(out_dir, exist_ok=True)
    write_csv(rows, os.path.join(out_dir, "bsp_table.csv"))
