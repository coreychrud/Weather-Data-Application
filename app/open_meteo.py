import asyncio
import math
from collections import OrderedDict
from datetime import date
from time import monotonic
from typing import Any

import httpx

from app.models import HeatmapPoint, UnitSystem


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
        self._heatmap_cache: OrderedDict[tuple, tuple[float, list[dict]]] = OrderedDict()
        self._heatmap_slots = asyncio.Semaphore(2)

    async def get_heatmap(
        self, *, weather_date: date, points: list[HeatmapPoint], source: str
    ) -> list[dict[str, Any]]:
        """Fetch only daily aggregates, in bounded batches; cache canonical SI values."""
        async def batch(batch_points: list[HeatmapPoint]) -> list[dict[str, Any]]:
            key = (
                source, weather_date,
                tuple((p.latitude, p.longitude) for p in batch_points),
            )
            async with self._heatmap_slots:
                cached = self._heatmap_cache.get(key)
                if cached and cached[0] > monotonic():
                    self._heatmap_cache.move_to_end(key)
                    return cached[1]

                params = {
                    "latitude": ",".join(str(p.latitude) for p in batch_points),
                    "longitude": ",".join(str(p.longitude) for p in batch_points),
                    "daily": "temperature_2m_mean,precipitation_sum",
                    "start_date": weather_date.isoformat(),
                    "end_date": weather_date.isoformat(),
                    "timezone": "auto",
                }
                url = (
                    f"{self._historical_base_url}/archive" if source == "historical"
                    else f"{self._forecast_base_url}/forecast"
                )
                payload = await self._request(url, params)
                locations = [payload] if isinstance(payload, dict) else payload
                if len(locations) != len(batch_points):
                    raise OpenMeteoResponseError

                samples = []
                for index, (point, location) in enumerate(zip(batch_points, locations)):
                    if not isinstance(location, dict):
                        raise OpenMeteoResponseError
                    daily = location.get("daily")
                    units = location.get("daily_units")
                    if (
                        not isinstance(daily, dict)
                        or not isinstance(units, dict)
                        or daily.get("time") != [weather_date.isoformat()]
                        or units.get("temperature_2m_mean") != "°C"
                        or units.get("precipitation_sum") != "mm"
                        or location.get("location_id", index) != index
                    ):
                        raise OpenMeteoResponseError
                    sample = point.model_dump()
                    for output, variable in (
                        ("temperature", "temperature_2m_mean"),
                        ("precipitation", "precipitation_sum"),
                    ):
                        values = daily.get(variable)
                        if not isinstance(values, list) or len(values) != 1:
                            raise OpenMeteoResponseError
                        value = values[0]
                        if value is not None and (
                            type(value) not in (int, float)
                            or not math.isfinite(value)
                            or (output == "precipitation" and value < 0)
                        ):
                            raise OpenMeteoResponseError
                        sample[output] = value
                    samples.append(sample)

                ttl = 86400 if source == "historical" else 900
                self._heatmap_cache[key] = (monotonic() + ttl, samples)
                self._heatmap_cache.move_to_end(key)
                while len(self._heatmap_cache) > 128:
                    self._heatmap_cache.popitem(last=False)
                return samples

        batches = await asyncio.gather(
            *(batch(points[i:i + 50]) for i in range(0, len(points), 50))
        )
        return [sample for group in batches for sample in group]

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

    async def get_historical_weather_for_month(
        self,
        *,
        month_start: date,
        month_end: date,
        latitude: float,
        longitude: float,
        timezone: str,
        units: UnitSystem,
    ) -> dict[str, Any]:
        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min",
            "start_date": month_start.isoformat(),
            "end_date": month_end.isoformat(),
            "timezone": timezone,
        }
        params.update(self._unit_params(units))
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

    async def search_locations(
        self, name: str, count: int = 5
    ) -> list[dict[str, Any]]:
        """Find geographic coordinates for a place name."""
        payload = await self._get(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": name, "count": count, "language": "en", "format": "json"},
        )

        results = payload.get("results", [])
        if not isinstance(results, list):
            raise OpenMeteoResponseError

        locations = []
        for result in results:
            if not isinstance(result, dict):
                raise OpenMeteoResponseError

            latitude = result.get("latitude")
            longitude = result.get("longitude")
            place_name = result.get("name")

            if (
                not isinstance(place_name, str)
                or not isinstance(latitude, (int, float))
                or not isinstance(longitude, (int, float))
                or isinstance(latitude, bool)
                or isinstance(longitude, bool)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise OpenMeteoResponseError

            locations.append({
                "name": place_name,
                "latitude": latitude,
                "longitude": longitude,
                "admin1": result.get("admin1"),
                "country": result.get("country"),
            })

        return locations

    async def _get(
        self, url: str, params: dict[str, str | int | float]
    ) -> dict[str, Any]:
        payload = await self._request(url, params)
        if not isinstance(payload, dict):
            raise OpenMeteoResponseError
        return payload

    async def _request(
        self, url: str, params: dict[str, str | int | float]
    ) -> dict[str, Any] | list[Any]:
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

        if not isinstance(payload, (dict, list)):
            raise OpenMeteoResponseError
        return payload
