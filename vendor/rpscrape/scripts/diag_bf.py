"""Diagnostic: time a burst of sequential Betfair SP-file fetches and tally
status codes / errors, to see whether throttling is the slowdown."""
import time
import curl_cffi
from datetime import date, timedelta

base = 'https://promo.betfair.com/betfairsp/prices/dwbfprices'
regions = ['uk', 'ire', 'usa', 'aus', 'fr', 'uae']

# sample ~10 consecutive days around mid-2024 across all regions = 60 requests
start = date(2024, 6, 10)
codes = {}
errs = 0
t0 = time.time()
n = 0
for i in range(10):
    d = start + timedelta(days=i)
    f = d.strftime('%d%m%Y')
    for r in regions:
        url = f'{base}{r}win{f}.csv'
        n += 1
        try:
            resp = curl_cffi.get(url, timeout=20)
            codes[resp.status_code] = codes.get(resp.status_code, 0) + 1
        except Exception as e:
            errs += 1
            codes[type(e).__name__] = codes.get(type(e).__name__, 0) + 1
elapsed = time.time() - t0
print(f'{n} requests in {elapsed:.1f}s = {elapsed/n*1000:.0f} ms/req')
print('codes:', codes, 'errs:', errs)
