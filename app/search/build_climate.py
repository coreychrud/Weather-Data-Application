"""Build the climate table that discover searches rank cities against.

Downloads daily weather for the map's 30 major metros from the Open-Meteo
archive, then averages it into typical values for each calendar month:

    python -m app.search.build_climate              # 5 years, about 8 minutes
    python -m app.search.build_climate --years 10   # 10 years, about 70 minutes

Run it once and commit app/search/data/city_climate.json; nobody else needs to
run it. Raw downloads are cached in .climate-cache/, so an interrupted run
picks up where it stopped.

Why it's slow: Open-Meteo's free tier allows 600 calls a minute, 5,000 an
hour and 10,000 a day, and a request longer than two weeks counts as several
calls (5 years for one city is about 130). The script paces itself to stay
under those limits.
"""

import argparse
from collections import deque
from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
import re
import time

import httpx

from app.config import DEFAULT_OPEN_METEO_ARCHIVE_BASE_URL


PLACES_FILE = Path("frontend/src/places.js")
OUTPUT_FILE = Path("app/search/data/city_climate.json")
CACHE_DIR = Path(".climate-cache")
DAILY_VARIABLES = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum",
                   "snowfall_sum", "sunshine_duration")
RAINY_DAY_MM = 1.0  # a day with at least 1 mm of precipitation counts as rainy

# Stay a little under Open-Meteo's free limits.
MINUTE_BUDGET = 550
HOUR_BUDGET = 4800
DAY_BUDGET = 9500


@dataclass(frozen=True)
class City:
    """One map metro, with the same id, name and region as in places.js."""

    id: str       
    name: str      
    region: str    
    latitude: float
    longitude: float

def slugify(value: str) -> str:
    """Same as slugify() in places.js, so ids match the map's markers."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_cities(path: Path = PLACES_FILE) -> list[City]:
    """Read the 30 major metros from places.js, so this list matches the map.

    The majorMetros array in that file is written like JSON (double quotes,
    plain numbers), so after removing the trailing comma it parses with
    json.loads. Each row is [name, state, state FIPS, latitude, longitude, population].
    """
    source = path.read_text(encoding="utf-8")
    start = source.index("export const majorMetros = [") + len("export const majorMetros = ")
    end = source.index("\n]", start) + 2
    rows = json.loads(re.sub(r",\s*\]", "]", source[start:end]))
    return [City(f"metro-{index}-{slugify(name)}", name, region, latitude, longitude)
            for index, (name, region, _fips, latitude, longitude, _population)
            in enumerate(rows, start=1)]


def request_cost(start: date, end: date) -> float:
    """Open-Meteo's weighting: one call per two weeks of data (5 variables < 10)."""
    return max(1.0, ((end - start).days + 1) / 14)


def estimated_minutes(cost: float) -> int:
    """Full hours spent waiting for the hourly budget, plus minute-paced calls."""
    full_hours, remainder = divmod(cost, HOUR_BUDGET)
    return math.ceil(full_hours * 60 + remainder / MINUTE_BUDGET)


class Pacer:
    """Sliding-window rate limiter for weighted API calls."""

    def __init__(self, clock=time.monotonic, sleep=time.sleep) -> None:
        self._clock = clock
        self._sleep = sleep
        self._spent: deque[tuple[float, float]] = deque()  # (timestamp, cost)

    def _used(self, window: float, now: float) -> float:
        return sum(cost for stamp, cost in self._spent if now - stamp < window)

    def wait_for(self, cost: float) -> None:
        while True:
            now = self._clock()
            while self._spent and now - self._spent[0][0] >= 3600:
                self._spent.popleft()
            if (self._used(60, now) + cost <= MINUTE_BUDGET
                    and self._used(3600, now) + cost <= HOUR_BUDGET):
                self._spent.append((now, cost))
                return
            self._sleep(5)


def fetch_daily(client: httpx.Client, city: City, start: date, end: date,
                pacer: Pacer, cache_dir: Path = CACHE_DIR) -> dict:
    """Daily data for one city, from the cache if it was downloaded before."""
    cache_file = cache_dir / f"{city.id}_{start}_{end}.json"          # line 115
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    params = {
        "latitude": city.latitude, "longitude": city.longitude,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES), "timezone": "auto",
    }
    for attempt in range(5):
        pacer.wait_for(request_cost(start, end))
        response = client.get(f"{DEFAULT_OPEN_METEO_ARCHIVE_BASE_URL}/archive", params=params)
        if response.status_code == 429 or response.status_code >= 500:
            wait = 60 * (attempt + 1)
            print(f"    Open-Meteo returned {response.status_code}; waiting {wait}s")
            time.sleep(wait)
            continue
        response.raise_for_status()
        daily = response.json()["daily"]
        cache_dir.mkdir(exist_ok=True)
        cache_file.write_text(json.dumps(daily), encoding="utf-8")
        return daily
    raise RuntimeError(f"gave up on {city.name}, {city.region} after 5 attempts")


def monthly_normals(daily: dict) -> dict[str, list[float | None]]:
    """Average daily data into one value per calendar month (index 0 = January).

    Temperatures and sunshine are averaged per day; precipitation, snowfall and
    rainy days are totaled per month and then averaged across the years.
    """
    buckets: dict[int, dict[str, list[float]]] = {
        month: {"high": [], "low": [], "precip": [], "snow": [], "sun": []}
        for month in range(1, 13)
    }
    years: dict[int, set[int]] = {month: set() for month in range(1, 13)}

    for index, day in enumerate(daily["time"]):
        year, month = int(day[:4]), int(day[5:7])
        years[month].add(year)
        bucket = buckets[month]
        for key, variable in (("high", "temperature_2m_max"), ("low", "temperature_2m_min"),
                              ("precip", "precipitation_sum"), ("snow", "snowfall_sum"),
                              ("sun", "sunshine_duration")):
            value = daily[variable][index]
            if value is not None:
                bucket[key].append(value)

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    def per_year(total: float, month: int) -> float | None:
        return round(total / len(years[month]), 1) if years[month] else None

    return {
        "high_c": [mean(buckets[m]["high"]) for m in range(1, 13)],
        "low_c": [mean(buckets[m]["low"]) for m in range(1, 13)],
        "precip_mm": [per_year(sum(buckets[m]["precip"]), m) for m in range(1, 13)],
        "snow_cm": [per_year(sum(buckets[m]["snow"]), m) for m in range(1, 13)],
        "rainy_days": [per_year(sum(1 for v in buckets[m]["precip"] if v >= RAINY_DAY_MM), m)
                       for m in range(1, 13)],
        "sun_hours": [mean([seconds / 3600 for seconds in buckets[m]["sun"]])
                      for m in range(1, 13)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", type=int, default=5, help="how many full years to average")
    parser.add_argument("--end-year", type=int, default=date.today().year - 1,
                        help="last full year to include (default: last year)")
    parser.add_argument("--limit", type=int, default=0, help="only the first N cities (testing)")
    parser.add_argument("--out", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    cities = load_cities()
    if args.limit:
        cities = cities[: args.limit]
    start = date(args.end_year - args.years + 1, 1, 1)
    end = date(args.end_year, 12, 31)
    cached = sum((CACHE_DIR / f"{city.id}_{start}_{end}.json").exists() for city in cities)
    cost = request_cost(start, end) * (len(cities) - cached)
    print(f"{len(cities)} cities, {start} to {end}: about {cost:,.0f} API calls "
          f"({cached} cities already cached)")
    if cost > DAY_BUDGET:
        raise SystemExit(f"That's over the free daily limit; use fewer --years "
                         f"(each year is about {request_cost(date(2023, 1, 1), date(2023, 12, 31)) * len(cities):,.0f} calls).")
    minutes = estimated_minutes(cost)
    print(f"Estimated time: about {minutes} minute{'s' if minutes != 1 else ''}\n")

    pacer = Pacer()
    rows = []
    with httpx.Client(timeout=60) as client:
        for number, city in enumerate(cities, 1):
            print(f"[{number:>3}/{len(cities)}] {city.name}, {city.region}")
            daily = fetch_daily(client, city, start, end, pacer)
            rows.append({"id": city.id, "name": city.name, "region": city.region,
                         "latitude": city.latitude, "longitude": city.longitude,
                         **monthly_normals(daily)})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "source": "Open-Meteo Historical Weather API (ERA5 reanalysis)",
        "period": [start.isoformat(), end.isoformat()],
        "units": {"high_c": "°C, average daily high", "low_c": "°C, average daily low",
                  "precip_mm": "mm per month", "snow_cm": "cm per month",
                  "rainy_days": "days per month with at least 1 mm",
                  "sun_hours": "hours of sunshine per day"},
        "cities": rows,
    }, indent=1), encoding="utf-8")
    print(f"\nWrote {len(rows)} cities to {args.out}")


if __name__ == "__main__":
    main()