from datetime import date
from typing import Any

import httpx

from app.models import UnitSystem


CURRENT_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
)
HOURLY_VARIABLES = (
    "temperature_2m",
    "precipitation_probability",
    "weather_code",
)
DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "sunrise",
    "sunset",
)
DAY_HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
)
DAY_DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "sunrise",
    "sunset",
    "wind_speed_10m_max",
)


class OpenMeteoError(Exception):
    """Base class for errors communicating with Open-Meteo."""


class OpenMeteoTimeoutError(OpenMeteoError):
    """Raised when Open-Meteo does not respond before the configured timeout."""


class OpenMeteoResponseError(OpenMeteoError):
    """Raised when Open-Meteo returns an unsuccessful response."""


class OpenMeteoRequestError(OpenMeteoError):
    """Raised when Open-Meteo rejects request parameters."""


class OpenMeteoClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        forecast_base_url: str,
        historical_base_url: str = "https://archive-api.open-meteo.com/v1",
    ) -> None:
        self._http_client = http_client
        self._forecast_base_url = forecast_base_url.rstrip("/")
        self._historical_base_url = historical_base_url.rstrip("/")

    async def get_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        forecast_days: int,
        timezone: str,
        units: UnitSystem,
    ) -> dict[str, Any]:
        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(CURRENT_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),
            "daily": ",".join(DAILY_VARIABLES),
            "forecast_days": forecast_days,
            "timezone": timezone,
        }

        params.update(self._unit_params(units))

        return await self._get(f"{self._forecast_base_url}/forecast", params)

    async def get_forecast_for_day(
        self,
        *,
        weather_date: date,
        latitude: float,
        longitude: float,
        timezone: str,
        units: UnitSystem,
    ) -> dict[str, Any]:
        params = self._day_params(
            weather_date=weather_date,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            units=units,
        )
        return await self._get(f"{self._forecast_base_url}/forecast", params)

    async def get_historical_weather_for_day(
        self,
        *,
        weather_date: date,
        latitude: float,
        longitude: float,
        timezone: str,
        units: UnitSystem,
    ) -> dict[str, Any]:
        params = self._day_params(
            weather_date=weather_date,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            units=units,
        )
        return await self._get(f"{self._historical_base_url}/archive", params)

    @staticmethod
    def _day_params(
        *,
        weather_date: date,
        latitude: float,
        longitude: float,
        timezone: str,
        units: UnitSystem,
    ) -> dict[str, str | int | float]:
        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(DAY_HOURLY_VARIABLES),
            "daily": ",".join(DAY_DAILY_VARIABLES),
            "start_date": weather_date.isoformat(),
            "end_date": weather_date.isoformat(),
            "timezone": timezone,
        }
        params.update(OpenMeteoClient._unit_params(units))
        return params

    @staticmethod
    def _unit_params(units: UnitSystem) -> dict[str, str]:
        if units is UnitSystem.imperial:
            return {
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
            }
        return {}

    async def _get(
        self, url: str, params: dict[str, str | int | float]
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OpenMeteoTimeoutError from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.BAD_REQUEST:
                raise OpenMeteoRequestError from exc
            raise OpenMeteoResponseError from exc
        except httpx.HTTPError as exc:
            raise OpenMeteoResponseError from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenMeteoResponseError from exc

        if not isinstance(payload, dict):
            raise OpenMeteoResponseError
        return payload

