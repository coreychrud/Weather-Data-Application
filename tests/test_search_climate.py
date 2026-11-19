from datetime import date
import json

import httpx
import pytest

from app.search import build_climate
from app.search.build_climate import (
    City,
    Pacer,
    estimated_minutes,
    fetch_daily,
    load_cities,
    monthly_normals,
    request_cost,
)


def test_cities_are_the_maps_30_metros() -> None:
    cities = load_cities()
    assert len(cities) == len({city.id for city in cities}) == 30
    assert cities[0] == City("metro-1-new-york", "New York", "NY", 40.662712, -73.938677)
    names = {(city.name, city.region) for city in cities}
    assert ("Phoenix", "AZ") in names
    assert ("Washington", "DC") in names

def test_ids_match_places_js() -> None:
    by_name = {city.name: city.id for city in load_cities()}
    # The en dash and the period are replaced like places.js's slugify().
    assert by_name["Dallas–Fort Worth"] == "metro-4-dallas-fort-worth"
    assert by_name["Minneapolis–St. Paul"] == "metro-16-minneapolis-st-paul"
    assert by_name["Cincinnati"] == "metro-30-cincinnati"



def test_request_cost_follows_open_meteo_weighting() -> None:
    assert request_cost(date(2024, 1, 1), date(2024, 1, 7)) == 1
    assert request_cost(date(2024, 1, 1), date(2024, 1, 28)) == 2
    assert round(request_cost(date(2021, 1, 1), date(2025, 12, 31))) == 130


def test_time_estimate() -> None:
    assert estimated_minutes(3900) == 8          # 30 cities x 5 years: minute budget only
    assert estimated_minutes(7830) == 60 + 6     # 30 cities x 10 years: one hourly wait


def test_monthly_normals_average_days_and_total_months() -> None:
    days = ["2023-01-01", "2023-01-02", "2024-01-01", "2024-01-02", "2024-02-01"]
    daily = {
        "time": days,
        "temperature_2m_max": [10, 12, 14, 16, 20],
        "temperature_2m_min": [0, 2, 4, None, 8],
        "precipitation_sum": [5.0, 0.0, 1.0, 0.5, 0.0],
        "snowfall_sum": [0, 0, 2.0, 0, 0],
        "sunshine_duration": [36000, 18000, 36000, 18000, 7200],  # seconds
    }
    normals = monthly_normals(daily)
    assert normals["high_c"][0] == 13.0            # mean of 10, 12, 14, 16
    assert normals["low_c"][0] == 2.0              # the missing value is skipped
    assert normals["precip_mm"][0] == 3.2          # 6.5 mm over 2 Januarys
    assert normals["rainy_days"][0] == 1.0         # 5.0 and 1.0 mm days, over 2 years
    assert normals["snow_cm"][0] == 1.0
    assert normals["sun_hours"][0] == 7.5
    assert normals["sun_hours"][1] == 2.0
    assert normals["high_c"][2] is None            # no March data


def test_pacer_waits_when_the_minute_budget_is_used() -> None:
    now = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    pacer = Pacer(clock=lambda: now[0], sleep=sleep)
    for _ in range(4):
        pacer.wait_for(130)         # 520 of the 550 allowed per minute
    assert sleeps == []
    pacer.wait_for(130)             # the 5th city has to wait for the window to move              # the 8th city has to wait for the window to move
    assert 55 <= sum(sleeps) <= 65


def test_fetch_daily_requests_once_then_uses_the_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_climate.time, "sleep", lambda seconds: None)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429)       # rate limited once, then succeeds
        return httpx.Response(200, json={"daily": {"time": ["2024-01-01"]}})

    city = City("metro-25-austin", "Austin", "TX", 30.3, -97.75)
    pacer = Pacer(sleep=lambda seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = fetch_daily(client, city, date(2024, 1, 1), date(2024, 1, 31), pacer, tmp_path)
        second = fetch_daily(client, city, date(2024, 1, 1), date(2024, 1, 31), pacer, tmp_path)

    assert first == second == {"time": ["2024-01-01"]}
    assert len(requests) == 2               # the 429 retry, then nothing for the cached call
    params = requests[-1].url.params
    assert params["latitude"] == "30.3"
    assert params["start_date"] == "2024-01-01"
    assert "sunshine_duration" in params["daily"]
    assert json.loads((tmp_path / "metro-25-austin_2024-01-01_2024-01-31.json").read_text())