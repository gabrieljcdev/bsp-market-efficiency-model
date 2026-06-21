#!/usr/bin/env python3
"""Standalone Betfair SP-cache prefetch.

Decouples Betfair (which geo-blocks the VPN exit → HTTP 403) from RP scraping
(which needs the VPN to dodge RP's Fastly 406 edge block). Run this VPN-OFF on
the home/UK IP; it writes the exact same cache file that
``rpscrape.prepare_betfair`` would, so a later VPN-ON ``rpscrape`` run finds the
cache and never touches promo.betfair.com.

Usage (from the scripts/ dir):
    python prefetch_betfair.py <start YYYY-MM-DD> <end YYYY-MM-DD> <filename>
e.g.
    python prefetch_betfair.py 2024-01-01 2024-12-31 2024_01_01_2024_12_31
"""
import sys

import rpscrape  # safe to import: rpscrape.main() is guarded by __name__=='__main__'
from utils.paths import build_paths, RequestKey


def make_url(d: str) -> str:
    # utils.betfair.create_urls() derives the date range from url.split('/')[6],
    # so any URL with the date in slot 6 works as a synthetic seed.
    return f'https://www.racingpost.com/results/0/x/{d}/x'


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)

    start, end, filename = sys.argv[1], sys.argv[2], sys.argv[3]

    req = RequestKey(
        scope_kind='region',
        scope_value='gb',
        race_type='all',
        filename=filename,
    )
    paths = build_paths(req)

    if paths.betfair.exists():
        print(f'SKIP {filename}: Betfair cache already exists at {paths.betfair}')
        return

    race_urls = [make_url(start), make_url(end)]
    betfair = rpscrape.prepare_betfair(race_urls, paths)
    n = len(betfair.rows) if betfair else 0
    print(f'DONE {filename}: {n} BSP rows -> {paths.betfair}')


if __name__ == '__main__':
    main()
