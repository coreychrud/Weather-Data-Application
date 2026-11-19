import asyncio
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import UnitSystem
from app.search import ranking
from app.search.geocode import Geocoder, PlaceNotFoundError
from app.search.router import get_geocoder
from app.search.summary import depth, months_phrase, temperature
from tests.test_search_ranking import CLIMATE


TODAY = date(2026, 11, 18)  # a Wednesday

METROS = [
    {"id": "metro-1-new-york", "name": "New York", "region": "NY", "latitude": 40.66, "longitude": -73.94},
    {"id": "metro-4-dallas-fort-worth", "name": "Dallas–Fort Worth", "region": "TX",
     "latitude": 32.79, "longitude": -96.77},
    {"id": "metro-5-houston", "name": "Houston", "region": "TX", "latitude": 29.79, "longitude": -95.39},
    {"id": "metro-23-st-louis", "name": "St. Louis", "region": "MO", "latitude": 38.64, "longitude": -90.24},
]


def geocoding_api(results_by_name: dict[str, list[dict]]) -> httpx.MockTransport:
    """A fake Open-Meteo Geocoding API."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["countryCode"] == "US"
        return httpx.Response(200, json={"results": results_by_name.get(request.url.params["name"], [])})
    return httpx.MockTransport(handler)


COLLEGE_STATIONS = [
    {"name": "College Station", "latitude": 34.9, "longitude": -92.3, "admin1": "Arkansas"},
    {"name": "College Station", "latitude": 30.63, "longitude": -96.33, "admin1": "Texas"},
]


def make_geocoder() -> Geocoder:
    client = httpx.AsyncClient(transport=geocoding_api({"college station": COLLEGE_STATIONS,
                                                        "boise": [{"name": "Boise", "latitude": 43.6,
                                                                   "longitude": -116.2, "admin1": "Idaho"}]}))
    return Geocoder(client, METROS)


def resolve(name: str):
    return asyncio.run(make_geocoder().resolve(name))


# --- Geocoding ---------------------------------------------------------------

@pytest.mark.parametrize(
    ("name", "expected_id"),
    [
        ("New York", "metro-1-new-york"),
        ("NYC", "metro-1-new-york"),
        ("Dallas", "metro-4-dallas-fort-worth"),
        ("Dallas–Fort Worth", "metro-4-dallas-fort-worth"),
        ("st louis", "metro-23-st-louis"),
        ("Houston, TX", "metro-5-houston"),
        ("Texas", "metro-4-dallas-fort-worth"),      # a state alone -> its largest metro
    ],
)
def test_metros_and_nicknames_resolve_offline(name: str, expected_id: str) -> None:
    assert resolve(name).id == expected_id


def test_other_places_use_the_geocoding_api() -> None:
    boise = resolve("Boise")
    assert (boise.name, boise.region, boise.id) == ("Boise", "ID", None)
    texas = resolve("College Station, TX")             # filtered to the Texas result
    assert (texas.region, texas.latitude) == ("TX", 30.63)


def test_unknown_places_and_metro_free_states() -> None:
    with pytest.raises(PlaceNotFoundError):
        resolve("Atlantis")
    with pytest.raises(PlaceNotFoundError) as error:
        resolve("Wyoming")
    assert "try a city in Wyoming" in error.value.hint


# --- Formatting ---------------------------------------------------------------

def test_units_and_month_phrases() -> None:
    assert temperature(21.0, UnitSystem.imperial) == "70°F"
    assert temperature(21.4, UnitSystem.metric) == "21°C"
    assert depth(25.4, UnitSystem.imperial) == "1.0 in"
    assert months_phrase([]) == "year-round"
    assert months_phrase([7]) == "in July"
    assert months_phrase([1, 2, 12]) == "in winter"
    assert months_phrase([4, 5]) == "in April and May"


# --- The endpoint ---------------------------------------------------------------

@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(ranking, "load_climate", lambda path=None: CLIMATE)
    app = create_app()
    app.dependency_overrides[get_geocoder] = make_geocoder
    return TestClient(app)


def search(client: TestClient, query: str, **extra):
    return client.post("/api/v1/search", json={"query": query, "today": TODAY.isoformat(), **extra})


def test_discover_search(client) -> None:
    response = search(client, "sunny cities in July")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "discover"
    assert body["condition"] == "sunny"
    assert body["months"] == [7]
    assert [r["name"] for r in body["results"]][:2] == ["Phoenix", "Seattle"]
    assert body["results"][0]["highlight"] == "13.0 hours of sun a day"
    assert body["results"][0]["rank"] == 1
    assert len(body["locations"]) == 3                 # the top 3, for the map
    assert body["summary"].startswith("Phoenix, AZ has the most sunshine in July")


def test_all_year_discover_summary(client) -> None:
    body = search(client, "give me somewhere sunny for most of the year").json()
    assert body["months"] == []
    assert "12 of 12 months have at least 8 hours of sun a day" in body["summary"]


def test_discover_respects_units_and_regions(client) -> None:
    body = search(client, "hot cities in Texas in July", units="metric").json()
    assert body["region"] == "TX"
    assert body["results"][0]["high"] == "36°C"
    assert "Only 1 of the 5 metros is in Texas." in body["summary"]


def test_lookup_returns_the_view_and_places(client) -> None:
    body = search(client, "compare Dallas and Boise tomorrow").json()
    assert body["mode"] == "forecast"
    assert body["date"] == "2026-11-19"
    assert [(l["name"], l["region"], l["id"]) for l in body["locations"]] == [
        ("Dallas–Fort Worth", "TX", "metro-4-dallas-fort-worth"), ("Boise", "ID", None)]
    assert body["summary"] == ("Showing the forecast for Dallas–Fort Worth, TX and Boise, ID "
                               "on Thursday, November 19, 2026.")


def test_lookup_without_a_place(client) -> None:
    body = search(client, "what will the weather be on saturday").json()
    assert body["needs_location"] is True
    assert "Pick a location on the map" in body["summary"]


def test_heatmap(client) -> None:
    body = search(client, "precipitation heatmap of Texas yesterday").json()
    assert body["mode"] == "heatmap"
    assert body["region"] == "TX"
    assert body["metric"] == "precipitation"
    assert body["summary"] == "Showing daily total precipitation across Texas on November 17, 2026."


def test_today_comes_from_the_request(client) -> None:
    body = client.post("/api/v1/search", json={"query": "Boise tomorrow", "today": "2027-01-31"}).json()
    assert body["date"] == "2027-02-01"


def test_unknown_place_is_a_422(client) -> None:
    response = search(client, "weather in Atlantis tomorrow")
    assert response.status_code == 422
    assert "Atlantis" in response.json()["detail"]


def test_empty_query_is_rejected(client) -> None:
    assert search(client, "").status_code == 422

@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Austin", True),
        ("Springfield", True),
        ("Austin, TX", True),
        ("weather in Springfield?", True),
        ("what's the weather like in Boise", True),
        ("Houston tomorrow", False),
        ("is it sunny in Boise", False),
        ("current weather in Houston", False),
        ("Houston in celsius", False),
        ("compare Houston and Boise", False),
        ("Texas", False),
        ("sunny cities in July", False),
    ],
)
def test_place_only(client, query: str, expected: bool) -> None:
    body = search(client, query).json()
    assert body["place_only"] is expected


def test_place_only_skips_geocoding(client) -> None:
    body = search(client, "Springfield").json()
    assert body["place_query"] == "Springfield"
    assert body["locations"] == []                # the pick-list comes from the location search
    assert body["summary"] == "Choose the Springfield you mean."