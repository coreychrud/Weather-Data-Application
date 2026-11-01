import asyncio
from datetime import date, datetime, timedelta, timezone
from time import monotonic
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import httpx
import pytest

from app.dependencies import get_open_meteo_client
from app.main import create_app
from app.models import HeatmapPoint
from app.open_meteo import (
    OpenMeteoClient,
    OpenMeteoRequestError,
    OpenMeteoResponseError,
    OpenMeteoTimeoutError,
)


POINT = {"latitude": 41.8781, "longitude": -87.6298}


def daily_payload(day: str, temperature: float | None = 12.5) -> dict:
    return {
        "daily": {"time": [day], "temperature_2m_mean": [temperature], "precipitation_sum": [0.0]},
        "daily_units": {"temperature_2m_mean": "°C", "precipitation_sum": "mm"},
    }


@pytest.mark.parametrize("offset,source", [(-20, "historical"), (-5, "historical"), (-1, "recent"), (0, "forecast"), (15, "forecast")])
def test_heatmap_routes_dates_and_returns_canonical_units(offset: int, source: str) -> None:
    day = datetime.now(timezone.utc).date() + timedelta(days=offset)
    service = AsyncMock()
    service.get_heatmap.return_value = [{**POINT, "temperature": None, "precipitation": 0}]
    app = create_app()
    app.dependency_overrides[get_open_meteo_client] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/weather/heatmap", json={"weather_date": str(day), "points": [POINT]})
    assert response.status_code == 200
    assert response.json() == {
        "weather_date": str(day), "source": source, "temperature_unit": "°C", "precipitation_unit": "mm",
        "samples": [{**POINT, "temperature": None, "precipitation": 0}],
    }
    service.get_heatmap.assert_awaited_once_with(weather_date=day, points=[HeatmapPoint(**POINT)], source=source)


@pytest.mark.parametrize("body", [
    {"weather_date": "1939-12-31", "points": [POINT]},
    {"weather_date": str(datetime.now(timezone.utc).date() + timedelta(days=16)), "points": [POINT]},
    {"weather_date": "2020-02-30", "points": [POINT]},
    {"weather_date": "2020-01-01", "points": []},
    {"weather_date": "2020-01-01", "points": [POINT] * 385},
    {"weather_date": "2020-01-01", "points": [{"latitude": 91, "longitude": 0}]},
    {"weather_date": "2020-01-01", "points": [{"latitude": 0, "longitude": -181}]},
])
def test_rejects_invalid_heatmap_without_upstream_work(body: dict) -> None:
    service = AsyncMock()
    app = create_app()
    app.dependency_overrides[get_open_meteo_client] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/weather/heatmap", json=body)
    assert response.status_code == 422
    service.get_heatmap.assert_not_awaited()


@pytest.mark.parametrize("error,status", [(OpenMeteoTimeoutError, 504), (OpenMeteoResponseError, 502), (OpenMeteoRequestError, 422)])
def test_heatmap_gateway_errors(error: type[Exception], status: int) -> None:
    service = AsyncMock()
    service.get_heatmap.side_effect = error
    app = create_app()
    app.dependency_overrides[get_open_meteo_client] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/weather/heatmap", json={"weather_date": "2020-01-01", "points": [POINT]})
    assert response.status_code == status


def test_batches_in_order_with_bounded_concurrency_and_expiring_cache() -> None:
    calls = []
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        calls.append(request)
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        latitudes = request.url.params["latitude"].split(",")
        payloads = [{**daily_payload("2020-01-01", float(latitude)), "location_id": index}
                    for index, latitude in enumerate(latitudes)]
        active -= 1
        return httpx.Response(200, json=payloads if len(payloads) > 1 else payloads[0])

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = OpenMeteoClient(http_client, "https://forecast.example/v1", "https://archive.example/v1")
            points = [HeatmapPoint(latitude=i / 10, longitude=-87) for i in range(121)]
            options = {"weather_date": date(2020, 1, 1), "points": points, "source": "historical"}
            samples = await client.get_heatmap(**options)
            assert [sample["temperature"] for sample in samples] == [point.latitude for point in points]
            assert [sample["latitude"] for sample in samples] == [point.latitude for point in points]
            assert len(calls) == 3
            assert peak == 2
            assert await client.get_heatmap(**options) == samples
            assert len(calls) == 3
            for key, (_, payload) in client._heatmap_cache.items():
                client._heatmap_cache[key] = (monotonic() - 1, payload)
            await client.get_heatmap(**options)
            assert len(calls) == 6
    asyncio.run(run())
    assert all(request.url.host == "archive.example" for request in calls)
    assert [len(request.url.params["latitude"].split(",")) for request in calls[:3]] == [50, 50, 21]
    assert calls[0].url.params["timezone"] == "auto"
    assert calls[0].url.params["daily"] == "temperature_2m_mean,precipitation_sum"
    assert "hourly" not in calls[0].url.params


@pytest.mark.parametrize("source", ["recent", "forecast"])
def test_heatmap_uses_forecast_for_recent_and_future_dates(source: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "forecast.example"
        assert request.url.params["start_date"] == request.url.params["end_date"] == "2026-11-01"
        return httpx.Response(200, json=daily_payload("2026-11-01", None))

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = OpenMeteoClient(http_client, "https://forecast.example/v1")
            samples = await client.get_heatmap(weather_date=date(2026, 11, 1), points=[HeatmapPoint(**POINT)], source=source)
            assert samples == [{**POINT, "temperature": None, "precipitation": 0}]
    asyncio.run(run())


@pytest.mark.parametrize("change", ["count", "date", "units", "values", "infinite", "boolean", "negative_precipitation", "location_id"])
def test_rejects_malformed_daily_samples_instead_of_miscoloring_the_map(change: str) -> None:
    payload = daily_payload("2020-01-01")
    if change == "date":
        payload["daily"]["time"] = ["2020-01-02"]
    if change == "units":
        payload["daily_units"]["temperature_2m_mean"] = "°F"
    if change == "values":
        payload["daily"]["temperature_2m_mean"] = []
    if change == "infinite":
        payload["daily"]["temperature_2m_mean"] = [float("inf")]
    if change == "boolean":
        payload["daily"]["temperature_2m_mean"] = [True]
    if change == "negative_precipitation":
        payload["daily"]["precipitation_sum"] = [-1]
    if change == "location_id":
        payload["location_id"] = 5

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        return httpx.Response(200, content=json.dumps([] if change == "count" else payload))

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = OpenMeteoClient(http_client, "https://forecast.example/v1")
            with pytest.raises(OpenMeteoResponseError):
                await client.get_heatmap(weather_date=date(2020, 1, 1), points=[HeatmapPoint(**POINT)], source="historical")
            assert not client._heatmap_cache
    asyncio.run(run())
