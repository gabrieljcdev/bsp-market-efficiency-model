"""PRO Betfair historical stream reader + order-book reconstruction (Gate 1).

Streams bz2-in-tar from ``data/historical/betfair_pro/`` **without ever extracting
the tars**, reconstructs per-market order-book state from the raw ``atb``/``atl``/``trd``
deltas at 1-second resolution, and classifies GB **flat WIN** markets by
self-classification from the Betfair ``marketDefinition`` (race-metadata does not reach
the 2015-16 era; see ``analysis/preregistration_inrunning.md`` §3 and the Gate-1 report).

Stdlib-only (no pandas / betfairlightweight) so the unit tests run in any venv. The
hand-rolled reconstruction is cross-checked against betfairlightweight separately.

Delta semantics (Betfair Exchange Stream):
  * ``mcm`` message: ``{"pt": <ms>, "mc": [ <marketChange> ]}``
  * marketChange: ``{"id","marketDefinition"?,"rc":[...],"img"?}`` — ``img`` = full image.
  * runnerChange: ``{"id": selId, "atb":[[price,size]], "atl":[...], "trd":[...]}``
  * ``atb``/``atl``/``trd`` are **absolute set-at-price** deltas: size 0 removes the level,
    else it replaces the size at that price (NOT additive).
  * best available to BACK = highest price offered; best to LAY = lowest price offered.
"""
from __future__ import annotations

import bz2
import json
import re
import tarfile
from typing import Dict, Iterator, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Betfair price ladder (for 1-tick slippage in the fill model, pre-reg §6)     #
# --------------------------------------------------------------------------- #
_TICK_BANDS = [
    (1.0, 2.0, 0.01), (2.0, 3.0, 0.02), (3.0, 4.0, 0.05), (4.0, 6.0, 0.10),
    (6.0, 10.0, 0.20), (10.0, 20.0, 0.50), (20.0, 30.0, 1.0), (30.0, 50.0, 2.0),
    (50.0, 100.0, 5.0), (100.0, 1000.0, 10.0),
]


def _inc_at(price: float) -> float:
    for lo, hi, inc in _TICK_BANDS:
        if lo <= price < hi:
            return inc
    return 0.01 if price < 1.0 else 10.0


def ticks_move(price: float, n: int) -> float:
    """Move ``n`` Betfair ticks from ``price`` (n<0 = down). Snapped to 2 dp / band."""
    p = round(price, 2)
    step = 1 if n >= 0 else -1
    for _ in range(abs(n)):
        inc = _inc_at(p - 1e-9) if step < 0 else _inc_at(p)
        p = round(p + step * inc, 2)
        p = max(1.01, min(1000.0, p))
    return p

# --------------------------------------------------------------------------- #
# Flat / jumps self-classification (marketDefinition-name based, WIN GB only)  #
# --------------------------------------------------------------------------- #

# Tokens that mark a JUMPS race (National Hunt): hurdle / chase / NH-flat (bumper).
_JUMP_TOKENS = {"hrd", "hurdle", "ch", "chs", "chase", "nhf", "inhf", "bumper"}


def classify_flat_jumps(name: Optional[str]) -> Optional[str]:
    """'flat' | 'jumps' | None (unclassifiable) from a Betfair race market name.

    Jumps names carry a code token (``2m Hrd``, ``2m4f Ch``, ``2m Nov Ch``, ``NH Flat``,
    ``2m NHF``); flat names do not (``5f Mdn Stks``, ``1m App Hcap``, ``6f Hcap``).
    """
    if not name:
        return None
    toks = re.findall(r"[a-z]+", name.lower())
    if not toks:
        return None
    if "nh" in toks and "flat" in toks:  # "NH Flat" = bumper = jumps
        return "jumps"
    if any(t in _JUMP_TOKENS for t in toks):
        return "jumps"
    return "flat"


def _norm_course(s: str) -> str:
    """Normalise a course string: drop a trailing ``(AW)``/``(July)`` qualifier, lower."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", s or "").strip().lower()


def load_gb_courses(path: str) -> set:
    """Set of normalised GB course names from data/reference/course_geometry.csv."""
    import csv

    out = set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            c = _norm_course(row.get("course", ""))
            if c:
                out.add(c)
    return out


# Exclusion reasons (also the coverage-counter keys). 'flat' is the sole inclusion.
def market_verdict(md: dict, gb_courses: set) -> Tuple[Optional[str], str]:
    """Return ('flat','flat') to INCLUDE, else (None, <reason>) to EXCLUDE-and-count."""
    if md is None:
        return None, "no_market_definition"
    if str(md.get("eventTypeId")) != "7":
        return None, "not_horse_racing"
    if md.get("marketType") != "WIN":          # excludes SPECIAL / PLACE / other
        return None, "not_win"
    if md.get("countryCode") != "GB":          # GB only; IE etc. excluded
        return None, "not_gb"
    venue = md.get("venue")
    if not venue or _norm_course(venue) not in gb_courses:
        return None, "venue_not_in_gb_ref"
    fj = classify_flat_jumps(md.get("name"))
    if fj == "jumps":
        return None, "jumps"
    if fj is None:
        return None, "unclassifiable_name"
    return "flat", "flat"


# --------------------------------------------------------------------------- #
# Order-book reconstruction from raw deltas                                    #
# --------------------------------------------------------------------------- #

class RunnerBook:
    """Per-runner back/lay/traded ladders reconstructed from set-at-price deltas."""

    __slots__ = ("back", "lay", "trd")

    def __init__(self) -> None:
        self.back: Dict[float, float] = {}
        self.lay: Dict[float, float] = {}
        self.trd: Dict[float, float] = {}

    @staticmethod
    def _apply(book: Dict[float, float], deltas) -> None:
        for pair in deltas or ():
            price, size = pair[0], pair[1]
            if size == 0:
                book.pop(price, None)
            else:
                book[price] = size

    def apply_rc(self, rc: dict) -> None:
        self._apply(self.back, rc.get("atb"))
        self._apply(self.lay, rc.get("atl"))
        self._apply(self.trd, rc.get("trd"))

    def best_back(self, n: int = 3) -> List[Tuple[float, float]]:
        """Best-n back prices (highest first)."""
        return sorted(self.back.items(), key=lambda kv: -kv[0])[:n]

    def best_lay(self, n: int = 3) -> List[Tuple[float, float]]:
        """Best-n lay prices (lowest first)."""
        return sorted(self.lay.items(), key=lambda kv: kv[0])[:n]

    def traded_total(self) -> float:
        return round(sum(self.trd.values()), 2)

    def traded_at_or_below(self, price: float) -> float:
        """Total traded volume at prices <= ``price`` (for the <=2.0 in-running touch)."""
        return round(sum(s for p, s in self.trd.items() if p <= price + 1e-9), 2)

    def matchable_back(self, price: float, slip_ticks: int = 1) -> float:
        """£ you could BACK at ~``price`` right now, allowing ``slip_ticks`` worse odds.

        Backing crosses into available-to-back rungs at price >= (price - slip). Sums
        the size resting at or through your level (pre-reg §6 'available at or through
        your price within slippage S').
        """
        limit = ticks_move(price, -slip_ticks)
        return round(sum(s for p, s in self.back.items() if p >= limit - 1e-9), 2)

    def matchable_lay(self, price: float, slip_ticks: int = 1) -> float:
        """£ you could LAY at ~``price`` right now, allowing ``slip_ticks`` worse odds.

        Laying crosses into available-to-lay rungs at price <= (price + slip)."""
        limit = ticks_move(price, slip_ticks)
        return round(sum(s for p, s in self.lay.items() if p <= limit + 1e-9), 2)


class Market:
    """Running reconstruction of one market across its message stream."""

    def __init__(self) -> None:
        self.definition: Optional[dict] = None
        self.market_id: Optional[str] = None
        self.status: Optional[str] = None
        self.inplay: bool = False
        self.bet_delay: Optional[int] = None
        self.market_time: Optional[str] = None
        self.suspend_time: Optional[str] = None
        self.publish_time: Optional[int] = None
        self.books: Dict[int, RunnerBook] = {}

    def apply_mcm(self, msg: dict) -> None:
        if "pt" in msg:
            self.publish_time = msg["pt"]
        for mc in msg.get("mc", []):
            if self.market_id is None:
                self.market_id = mc.get("id")
            if mc.get("img"):            # full image => reset reconstructed books
                self.books.clear()
            md = mc.get("marketDefinition")
            if md:
                self.definition = md
                self.status = md.get("status", self.status)
                self.inplay = md.get("inPlay", self.inplay)
                self.bet_delay = md.get("betDelay", self.bet_delay)
                self.market_time = md.get("marketTime", self.market_time)
                self.suspend_time = md.get("suspendTime", self.suspend_time)
                # seed a book for every ACTIVE runner so zero-liquidity runners are
                # tracked (matches betfairlightweight, which lists all runners).
                for rd in md.get("runners", []):
                    if rd.get("status") == "ACTIVE" and rd.get("id") not in self.books:
                        self.books[rd["id"]] = RunnerBook()
            for rc in mc.get("rc", []):
                sid = rc.get("id")
                book = self.books.get(sid)
                if book is None:
                    book = self.books[sid] = RunnerBook()
                book.apply_rc(rc)


def snapshot(m: Market, n_depth: int = 3) -> dict:
    """Light snapshot of the market at the current reconstructed instant."""
    runners = {}
    for sid, book in m.books.items():
        runners[sid] = {
            "back": book.best_back(n_depth),
            "lay": book.best_lay(n_depth),
            "trd": book.traded_total(),
        }
    return {
        "market_id": m.market_id,
        "pt": m.publish_time,
        "status": m.status,
        "inplay": m.inplay,
        "bet_delay": m.bet_delay,
        "runners": runners,
    }


def iter_snapshots(messages: Iterator[dict], step_ms: int = 1000,
                   n_depth: int = 3) -> Iterator[dict]:
    """Yield reconstructed snapshots at ~1s cadence.

    Always emits on the first message, whenever >= ``step_ms`` has elapsed since the
    last emit, and additionally on any inplay-flag or market-status transition
    (so in-running entry and suspensions are never missed by the sampling grid).
    """
    m = Market()
    last_emit: Optional[int] = None
    prev_inplay = False
    prev_status: Optional[str] = None
    for msg in messages:
        m.apply_mcm(msg)
        pt = m.publish_time
        if pt is None:
            continue
        emit = (
            last_emit is None
            or pt - last_emit >= step_ms
            or m.inplay != prev_inplay
            or m.status != prev_status
        )
        if emit:
            yield snapshot(m, n_depth)
            last_emit = pt
            prev_inplay = m.inplay
            prev_status = m.status


# --------------------------------------------------------------------------- #
# Streaming bz2-in-tar (never extract the tar)                                 #
# --------------------------------------------------------------------------- #

def iter_tar_market_streams(tar_paths: List[str]) -> Iterator[Tuple[str, str, List[dict]]]:
    """Yield (tar_path, market_id, [parsed messages]) for each ``1.*.bz2`` member.

    Uses ``TarFile.extractfile`` (in-memory file object) + ``bz2.decompress`` — the tar
    is streamed, never expanded to disk. Event-metadata members (``<eventId>.bz2``) are
    skipped; only market files (``1.*.bz2``) are yielded.
    """
    for tp in tar_paths:
        with tarfile.open(tp) as tar:
            for member in tar:
                base = member.name.rsplit("/", 1)[-1]
                if not (member.name.endswith(".bz2") and base.startswith("1.")):
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                try:
                    raw = bz2.decompress(fh.read())
                except Exception:
                    continue
                msgs: List[dict] = []
                for line in raw.decode("utf-8", "replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msgs.append(json.loads(line))
                    except Exception:
                        continue
                yield tp, base[:-4], msgs


def first_market_definition(messages: List[dict]) -> Optional[dict]:
    """First ``marketDefinition`` in a message list (for classification / counting)."""
    for msg in messages:
        for mc in msg.get("mc", []):
            md = mc.get("marketDefinition")
            if md:
                return md
    return None


def peek_market_definition(fileobj, chunk: int = 65536) -> Optional[dict]:
    """First ``marketDefinition`` by decompressing only enough of the bz2 to reach it.

    Phase-A optimisation: the marketDefinition is in the opening image message, so we
    stream-decompress block by block and stop at the first line that carries it —
    avoiding a full decompress of multi-MB in-running markets just to classify them.
    ``fileobj`` is a binary file-like (e.g. ``TarFile.extractfile(member)``).
    """
    dec = bz2.BZ2Decompressor()
    buf = b""
    while True:
        raw = fileobj.read(chunk)
        if not raw:
            break
        try:
            buf += dec.decompress(raw)
        except (OSError, EOFError):
            break
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if b"marketDefinition" in line:
                try:
                    for mc in json.loads(line).get("mc", []):
                        if mc.get("marketDefinition"):
                            return mc["marketDefinition"]
                except Exception:
                    return None
    if b"marketDefinition" in buf:      # last line, no trailing newline
        try:
            for mc in json.loads(buf).get("mc", []):
                if mc.get("marketDefinition"):
                    return mc["marketDefinition"]
        except Exception:
            return None
    return None


def iter_gb_flat_markets(tar_paths: List[str], gb_courses: set):
    """Yield (tar, market_id, verdict_reason, member) — classifying via a partial
    decompress first, so non-GB-flat markets are rejected cheaply. For an INCLUDED
    market the caller re-reads the member fully (see gate runner). Coverage counters
    are the caller's responsibility.
    """
    for tp in tar_paths:
        with tarfile.open(tp) as tar:
            for member in tar:
                base = member.name.rsplit("/", 1)[-1]
                if not (member.name.endswith(".bz2") and base.startswith("1.")):
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                md = peek_market_definition(fh)
                verdict, reason = market_verdict(md, gb_courses) if md else (None, "no_md")
                yield tp, base[:-4], reason, (tp, member.name)
