from unittest.mock import AsyncMock
from datetime import date

from fastapi.testclient import TestClient

from app.dependencies import get_open_meteo_client
from app.main import create_app
from app.models import UnitSystem
from app.open_meteo import (
    OpenMeteoRequestError,
    OpenMeteoResponseError,
    OpenMeteoTimeoutError,
)


FORECAST_PAYLOAD = {
    "latitude": 41.875,
    "longitude": -87.625,
    "generationtime_ms": 0.12,
    "utc_offset_seconds": -18000,
    "timezone": "America/Chicago",
    "timezone_abbreviation": "CDT",
    "elevation": 180.0,
    "current_units": {
        "time": "iso8601",
        "interval": "seconds",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°C",
        "is_day": "",
        "precipitation": "mm",
        "weather_code": "wmo code",
        "wind_speed_10m": "km/h",
    },
    "current": {
        "time": "2026-10-26T12:00",
        "interval": 900,
        "temperature_2m": 12.3,
        "relative_humidity_2m": 71,
        "apparent_temperature": 10.8,
        "is_day": 1,
        "precipitation": 0.0,
        "weather_code": 3,
        "wind_speed_10m": 14.2,
    },
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "precipitation_probability": "%",
        "weather_code": "wmo code",
    },
    "hourly": {
        "time": ["2026-10-26T12:00"],
        "temperature_2m": [12.3],
        "precipitation_probability": [10],
        "weather_code": [3],
    },
    "daily_units": {
        "time": "iso8601",
        "weather_code": "wmo code",
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "precipitation_probability_max": "%",
        "sunrise": "iso8601",
        "sunset": "iso8601",
    },
    "daily": {
        "time": ["2026-10-26"],
        "weather_code": [3],
        "temperature_2m_max": [14.0],
        "temperature_2m_min": [7.2],
        "precipitation_probability_max": [10],
        "sunrise": ["2026-10-26T07:17"],
        "sunset": ["2026-10-26T17:53"],
    },
}

DAY_PAYLOAD = {
    "latitude": 41.875,
    "longitude": -87.625,
    "generationtime_ms": 0.15,
    "utc_offset_seconds": -18000,
    "timezone": "America/Chicago",
    "timezone_abbreviation": "CDT",
    "elevation": 180.0,
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "precipitation": "mm",
        "weather_code": "wmo code",
        "wind_speed_10m": "km/h",
    },
    "hourly": {
        "time": ["2026-10-27T00:00"],
        "temperature_2m": [9.2],
        "relative_humidity_2m": [78],
        "precipitation": [0.0],
        "weather_code": [2],
        "wind_speed_10m": [8.4],
    },
    "daily_units": {
        "time": "iso8601",
        "weather_code": "wmo code",
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "precipitation_sum": "mm",
        "sunrise": "iso8601",
        "sunset": "iso8601",
        "wind_speed_10m_max": "km/h",
    },
    "daily": {
        "time": ["2026-10-27"],
        "weather_code": [2],
        "temperature_2m_max": [15.1],
        "temperature_2m_min": [8.7],
        "precipitation_sum": [0.0],
        "sunrise": ["2026-10-27T07:18"],
        "sunset": ["2026-10-27T17:51"],
        "wind_speed_10m_max": [15.3],
    },
}


def make_client(service: AsyncMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_open_meteo_client] = lambda: service
    return TestClient(app)


def test_health_check() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_forecast() -> None:
    service = AsyncMock()
    service.get_forecast.return_value = FORECAST_PAYLOAD

    with make_client(service) as client:
        response = client.get(
            "/api/v1/forecast",
            params={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "forecast_days": 3,
                "units": "imperial",
            },
        )

    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Chicago"
    service.get_forecast.assert_awaited_once_with(
        latitude=41.8781,
        longitude=-87.6298,
        forecast_days=3,
        timezone="auto",
        units=UnitSystem.imperial,
    )


def test_rejects_invalid_coordinates() -> None:
    service = AsyncMock()

    with make_client(service) as client:
        response = client.get(
            "/api/v1/forecast",
            params={"latitude": 91, "longitude": -87.6298},
        )

    assert response.status_code == 422
    service.get_forecast.assert_not_awaited()


def test_get_forecast_for_day() -> None:
    service = AsyncMock()
    service.get_forecast_for_day.return_value = DAY_PAYLOAD

    with make_client(service) as client:
        response = client.get(
            "/api/v1/weather/forecast/2026-10-27",
            params={"latitude": 41.8781, "longitude": -87.6298},
        )

    assert response.status_code == 200
    assert response.json()["category"] == "forecast"
    service.get_forecast_for_day.assert_awaited_once_with(
        weather_date=date(2026, 10, 27),
        latitude=41.8781,
        longitude=-87.6298,
        timezone="auto",
        units=UnitSystem.metric,
    )


def test_get_historical_weather_for_day() -> None:
    service = AsyncMock()
    service.get_historical_weather_for_day.return_value = DAY_PAYLOAD

    with make_client(service) as client:
        response = client.get(
            "/api/v1/weather/historical/2020-01-15",
            params={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "units": "imperial",
            },
        )

    assert response.status_code == 200
    assert response.json()["category"] == "historical"
    service.get_historical_weather_for_day.assert_awaited_once_with(
        weather_date=date(2020, 1, 15),
        latitude=41.8781,
        longitude=-87.6298,
        timezone="auto",
        units=UnitSystem.imperial,
    )


def test_rejects_malformed_weather_date() -> None:
    service = AsyncMock()

    with make_client(service) as client:
        response = client.get(
            "/api/v1/weather/forecast/not-a-date",
            params={"latitude": 41.8781, "longitude": -87.6298},
        )

    assert response.status_code == 422
    service.get_forecast_for_day.assert_not_awaited()


def test_translates_rejected_day_request() -> None:
    service = AsyncMock()
    service.get_forecast_for_day.side_effect = OpenMeteoRequestError

    with make_client(service) as client:
        response = client.get(
            "/api/v1/weather/forecast/1940-01-01",
            params={"latitude": 41.8781, "longitude": -87.6298},
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Open-Meteo rejected the date or request parameters"
    }


def test_translates_upstream_timeout() -> None:
    service = AsyncMock()
    service.get_forecast.side_effect = OpenMeteoTimeoutError

    with make_client(service) as client:
        response = client.get(
            "/api/v1/forecast",
            params={"latitude": 41.8781, "longitude": -87.6298},
        )

    assert response.status_code == 504
    assert response.json() == {"detail": "Open-Meteo timed out"}


def test_translates_rejected_forecast_request() -> None:
    service = AsyncMock()
    service.get_forecast.side_effect = OpenMeteoRequestError

    with make_client(service) as client:
        response = client.get(
            "/api/v1/forecast",
            params={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "timezone": "invalid/timezone",
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Open-Meteo rejected the request parameters"
    }


def test_translates_invalid_upstream_response() -> None:
    service = AsyncMock()
    service.get_forecast.side_effect = OpenMeteoResponseError

    with make_client(service) as client:
        response = client.get(
            "/api/v1/forecast",
            params={"latitude": 41.8781, "longitude": -87.6298},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Open-Meteo returned an invalid response"
    }

