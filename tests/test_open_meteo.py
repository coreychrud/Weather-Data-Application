import asyncio
from datetime import date

import httpx
import pytest

from app.models import UnitSystem
from app.open_meteo import (
    OpenMeteoClient,
    OpenMeteoResponseError,
    OpenMeteoTimeoutError,
)


def test_requests_imperial_forecast_options() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"latitude": 41.875})

    async def run() -> dict[str, object]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = OpenMeteoClient(http_client, "https://example.test/v1/")
            return await client.get_forecast(
                latitude=41.8781,
                longitude=-87.6298,
                forecast_days=3,
                timezone="auto",
                units=UnitSystem.imperial,
            )

    payload = asyncio.run(run())

    assert payload == {"latitude": 41.875}
    assert captured_request is not None
    assert captured_request.url.path == "/v1/forecast"
    params = captured_request.url.params
    assert params["temperature_unit"] == "fahrenheit"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["forecast_days"] == "3"
    assert "temperature_2m" in params["current"]
    assert "temperature_2m_max" in params["daily"]


def test_requests_a_single_forecast_day() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"latitude": 41.875})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = OpenMeteoClient(
                http_client,
                "https://forecast.example/v1",
                "https://archive.example/v1",
            )
            await client.get_forecast_for_day(
                weather_date=date(2026, 10, 27),
                latitude=41.8781,
                longitude=-87.6298,
                timezone="auto",
                units=UnitSystem.metric,
            )

    asyncio.run(run())

    assert captured_request is not None
    assert captured_request.url.host == "forecast.example"
    assert captured_request.url.path == "/v1/forecast"
    params = captured_request.url.params
    assert params["start_date"] == "2026-10-27"
    assert params["end_date"] == "2026-10-27"
    assert "relative_humidity_2m" in params["hourly"]
    assert "precipitation_sum" in params["daily"]


def test_requests_a_single_historical_day() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"latitude": 41.875})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = OpenMeteoClient(
                http_client,
                "https://forecast.example/v1",
                "https://archive.example/v1",
            )
            await client.get_historical_weather_for_day(
                weather_date=date(2020, 1, 15),
                latitude=41.8781,
                longitude=-87.6298,
                timezone="auto",
                units=UnitSystem.imperial,
            )

    asyncio.run(run())

    assert captured_request is not None
    assert captured_request.url.host == "archive.example"
    assert captured_request.url.path == "/v1/archive"
    params = captured_request.url.params
    assert params["start_date"] == "2020-01-15"
    assert params["end_date"] == "2020-01-15"
    assert params["temperature_unit"] == "fahrenheit"


def test_translates_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = OpenMeteoClient(http_client, "https://example.test/v1")
            await client.get_forecast(
                latitude=0,
                longitude=0,
                forecast_days=1,
                timezone="auto",
                units=UnitSystem.metric,
            )

    with pytest.raises(OpenMeteoResponseError):
        asyncio.run(run())


def test_translates_timeouts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = OpenMeteoClient(http_client, "https://example.test/v1")
            await client.get_forecast(
                latitude=0,
                longitude=0,
                forecast_days=1,
                timezone="auto",
                units=UnitSystem.metric,
            )

    with pytest.raises(OpenMeteoTimeoutError):
        asyncio.run(run())
