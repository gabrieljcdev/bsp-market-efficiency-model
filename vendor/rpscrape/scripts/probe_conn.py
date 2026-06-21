from curl_cffi import requests as creq

for url in [
    "https://www.racingpost.com/results",
    "https://promo.betfair.com/betfairsp/prices",
]:
    try:
        r = creq.get(url, impersonate="chrome", timeout=15)
        print(url, "->", r.status_code)
    except Exception as e:
        print(url, "ERR", type(e).__name__, str(e)[:80])
