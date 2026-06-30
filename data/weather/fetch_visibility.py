"""Block 2 (reduced — visibility probe): fetch hourly weather incl. visibility
for every GB course-day in the joined dataset, from Open-Meteo's Historical
Forecast API (archived model runs).

WHY this source (not ERA5 archive): the ERA5 archive API returns visibility =
all-null. historical-forecast-api carries a real visibility field (units = m).
COVERAGE: visibility is only populated from ~2022-03-01 onward, so we fetch the
covered window only; earlier race-days get no weather (flagged downstream).

Strategy: ONE call per (course, year) over the covered window (~300 calls total),
not one per course-day (6k+). Cache each response as JSON so re-runs are free.
Polite: sleep between live calls, exponential back-off on HTTP 429.

Output: data/weather/weather_by_race.csv — one row per runner-race with the
weather at the nearest hour to the off, columns prefixed wx_.
"""
import csv, json, os, sys, time, urllib.request, urllib.error
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from course_coords import COORDS, lookup  # noqa: E402

JOINED = "data/joined/joined_gb_2018_2026.csv"
CACHE_DIR = "data/weather/cache"
OUT = "data/weather/weather_by_race.csv"
BASE = "https://historical-forecast-api.open-meteo.com/v1/forecast"

VIS_START = "2022-03-01"   # first date with populated visibility (probed)
DATA_END = "2026-06-19"    # dataset max date

# visibility is the probe target; temp/dewpoint give the temp-dewpoint spread
# (THE physical fog predictor, a cross-check on visibility) and wind disperses
# fog (plausible interaction). Trimmed from 9 -> 4 vars to roughly halve payload
# (full-range per-course calls are volume-bound). Re-fetch wider if vis shows signal.
HOURLY = [
    "visibility", "temperature_2m", "dew_point_2m", "wind_speed_10m",
]

SLEEP = 0.5
os.makedirs(CACHE_DIR, exist_ok=True)


def slug(course):
    return (course.replace(" ", "_").replace("(", "").replace(")", "")
            .replace("/", "_"))


def cache_path(course):
    return os.path.join(CACHE_DIR, f"{slug(course)}.json")


def fetch_course(course, start, end):
    """Fetch (or load cached) hourly data for one course across the full covered
    date range [start, end] in a SINGLE call. The API has high per-request
    latency (~10s fixed + ~hours), so one big call per course beats many small
    ones. Returns the parsed JSON dict."""
    path = cache_path(course)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    lat, lon = lookup(course)
    url = (f"{BASE}?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}"
           f"&hourly={','.join(HOURLY)}&timezone=Europe%2FLondon")

    backoff = 2.0
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                data = json.load(r)
            with open(path, "w") as f:
                json.dump(data, f)
            time.sleep(SLEEP)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"    429 backoff {backoff:.0f}s ({course} {year})")
                time.sleep(backoff)
                backoff *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # bare TimeoutError (socket read timeout) is NOT wrapped in URLError
            print(f"    net error {type(e).__name__}: {e}; retry in {backoff:.0f}s "
                  f"({course})", flush=True)
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError(f"Failed after retries: {course} {year}")


def build_hour_index(data):
    """Map 'YYYY-MM-DDTHH:00' -> {var: value} for fast nearest-hour lookup."""
    h = data.get("hourly", {})
    times = h.get("time", [])
    idx = {}
    for i, t in enumerate(times):
        idx[t] = {v: h.get(v, [None] * len(times))[i] for v in HOURLY}
    return idx


def main():
    # 1. per course, the min/max race date in the covered window (one call each)
    course_range = {}   # course -> [min_date, max_date] within covered window
    races = []          # (date, course, off) for every runner row
    with open(JOINED) as f:
        r = csv.reader(f)
        header = next(r)
        ci = {name: i for i, name in enumerate(header)}
        for row in r:
            date = row[ci["date"]]
            course = row[ci["course"]]
            off = row[ci["off"]]
            races.append((date, course, off))
            if date >= VIS_START:
                lo, hi = course_range.get(course, (date, date))
                course_range[course] = (min(lo, date), max(hi, date))

    total_calls = len(course_range)
    print(f"{total_calls} courses to fetch (one full-range call each, covered "
          f"window only)")

    # 2. fetch every course over its covered range, build a nested hour index
    idx = {}  # course -> {hourstamp: {var: val}}
    done = 0
    for course in sorted(course_range):
        lo, hi = course_range[course]
        start = max(lo, VIS_START)
        end = min(hi, DATA_END)
        data = fetch_course(course, start, end)
        idx[course] = build_hour_index(data)
        done += 1
        print(f"  fetched {done}/{total_calls}  {course} [{start}..{end}] "
              f"hours={len(idx[course])}", flush=True)

    # 3. join each runner-race to the weather at the nearest hour to its off
    out_cols = ["date", "course", "off", "wx_in_window"] + [f"wx_{v}" for v in HOURLY]
    n_rows = n_weather = 0
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(out_cols)
        for date, course, off in races:
            n_rows += 1
            in_window = 1 if date >= VIS_START else 0
            vals = {f"wx_{v}": "" for v in HOURLY}
            if in_window and course in idx:
                # nearest hour: round the off time to the closest hour
                try:
                    hh, mm = off.split(":")
                    hour = int(hh) + (1 if int(mm) >= 30 else 0)
                    hour = min(hour, 23)
                    stamp = f"{date}T{hour:02d}:00"
                    rec = idx[course].get(stamp)
                    if rec and rec.get("visibility") is not None:
                        for v in HOURLY:
                            vals[f"wx_{v}"] = rec.get(v)
                        n_weather += 1
                except ValueError:
                    pass
            w.writerow([date, course, off, in_window] + [vals[f"wx_{v}"] for v in HOURLY])

    print(f"\nwrote {OUT}")
    print(f"  runner rows total              : {n_rows}")
    print(f"  rows in covered window         : {sum(1 for d,_,_ in races if d>=VIS_START)}")
    print(f"  rows that got weather (vis)    : {n_weather}")


if __name__ == "__main__":
    main()
