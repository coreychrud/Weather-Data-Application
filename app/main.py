from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, status
import httpx

from app.config import Settings
from app.dependencies import OpenMeteoClientDependency
from app.models import (
    DayWeatherResponse,
    ForecastResponse,
    HealthResponse,
    HeatmapRequest,
    HeatmapResponse,
    MonthlyWeatherResponse,
    UnitSystem,
    WeatherCategory,
)
from app.open_meteo import (
    OpenMeteoClient,
    OpenMeteoRequestError,
    OpenMeteoResponseError,
    OpenMeteoTimeoutError,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(resolved_settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as http_client:
            app.state.open_meteo_client = OpenMeteoClient(
                http_client=http_client,
                forecast_base_url=resolved_settings.open_meteo_base_url,
                historical_base_url=resolved_settings.open_meteo_archive_base_url,
            )
            yield

    application = FastAPI(
        title="Weather Data API",
        description="A typed HTTP API backed by Open-Meteo forecasts.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Check whether the service is running",
    )
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.post(
        "/api/v1/weather/heatmap",
        response_model=HeatmapResponse,
        tags=["weather"],
        summary="Retrieve daily mean temperature and precipitation for up to 384 map samples",
    )
    async def heatmap(
        request: HeatmapRequest, client: OpenMeteoClientDependency
    ) -> dict[str, object]:
        today = datetime.now(datetime_timezone.utc).date()
        if not date(1940, 1, 1) <= request.weather_date <= today + timedelta(days=15):
            raise HTTPException(
                status_code=422,
                detail="Choose a date from 1940 through the next 15 days.",
            )
        # Bridge the archive's publication delay using the Forecast API's recent past.
        if request.weather_date <= today - timedelta(days=5):
            source = "historical"
        elif request.weather_date < today:
            source = "recent"
        else:
            source = "forecast"
        try:
            samples = await client.get_heatmap(
                weather_date=request.weather_date, points=request.points, source=source
            )
        except OpenMeteoRequestError as exc:
            raise HTTPException(
                status_code=422, detail="Weather data is unavailable for this date or area."
            ) from exc
        except OpenMeteoTimeoutError as exc:
            raise HTTPException(
                status_code=504, detail="Open-Meteo timed out. Try loading the map again."
            ) from exc
        except OpenMeteoResponseError as exc:
            raise HTTPException(
                status_code=502, detail="Open-Meteo returned an invalid heatmap response."
            ) from exc
        return {"weather_date": request.weather_date, "source": source, "samples": samples}

    @application.get(
        "/api/v1/forecast",
        response_model=ForecastResponse,
        tags=["weather"],
        summary="Retrieve a weather forecast for a coordinate",
    )
    async def forecast(
        client: OpenMeteoClientDependency,
        latitude: Annotated[float, Query(ge=-90, le=90, examples=[41.8781])],
        longitude: Annotated[float, Query(ge=-180, le=180, examples=[-87.6298])],
        forecast_days: Annotated[int, Query(ge=1, le=16)] = 7,
        timezone: Annotated[str, Query(min_length=1, max_length=100)] = "auto",
        units: UnitSystem = UnitSystem.metric,
    ) -> dict[str, object]:
        try:
            return await client.get_forecast(
                latitude=latitude,
                longitude=longitude,
                forecast_days=forecast_days,
                timezone=timezone,
                units=units,
            )
        except OpenMeteoRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Open-Meteo rejected the request parameters",
            ) from exc
        except OpenMeteoTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Open-Meteo timed out",
            ) from exc
        except OpenMeteoResponseError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Open-Meteo returned an invalid response",
            ) from exc

    async def day_weather(
        *,
        category: WeatherCategory,
        weather_date: date,
        latitude: float,
        longitude: float,
        timezone: str,
        units: UnitSystem,
        client: OpenMeteoClient,
    ) -> dict[str, object]:
        try:
            if category is WeatherCategory.forecast:
                payload = await client.get_forecast_for_day(
                    weather_date=weather_date,
                    latitude=latitude,
                    longitude=longitude,
                    timezone=timezone,
                    units=units,
                )
            else:
                payload = await client.get_historical_weather_for_day(
                    weather_date=weather_date,
                    latitude=latitude,
                    longitude=longitude,
                    timezone=timezone,
                    units=units,
                )
        except OpenMeteoRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Open-Meteo rejected the date or request parameters",
            ) from exc
        except OpenMeteoTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Open-Meteo timed out",
            ) from exc
        except OpenMeteoResponseError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Open-Meteo returned an invalid response",
            ) from exc

        return {**payload, "category": category}

    @application.get(
        "/api/v1/weather/forecast/{weather_date}",
        response_model=DayWeatherResponse,
        tags=["weather"],
        summary="Retrieve forecast weather for one day",
    )
    async def forecast_for_day(
        weather_date: Annotated[
            date,
            Path(
                description="Weather date in ISO 8601 format: YYYY-MM-DD.",
                examples=["2026-10-27"],
            ),
        ],
        client: OpenMeteoClientDependency,
        latitude: Annotated[float, Query(ge=-90, le=90, examples=[41.8781])],
        longitude: Annotated[float, Query(ge=-180, le=180, examples=[-87.6298])],
        timezone: Annotated[str, Query(min_length=1, max_length=100)] = "auto",
        units: UnitSystem = UnitSystem.metric,
    ) -> dict[str, object]:
        return await day_weather(
            category=WeatherCategory.forecast,
            weather_date=weather_date,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            units=units,
            client=client,
        )

    @application.get(
        "/api/v1/weather/historical/{weather_date}",
        response_model=DayWeatherResponse,
        tags=["weather"],
        summary="Retrieve historical weather for one day",
    )
    async def historical_weather_for_day(
        weather_date: Annotated[
            date,
            Path(
                description="Weather date in ISO 8601 format: YYYY-MM-DD.",
                examples=["2020-01-15"],
            ),
        ],
        client: OpenMeteoClientDependency,
        latitude: Annotated[float, Query(ge=-90, le=90, examples=[41.8781])],
        longitude: Annotated[float, Query(ge=-180, le=180, examples=[-87.6298])],
        timezone: Annotated[str, Query(min_length=1, max_length=100)] = "auto",
        units: UnitSystem = UnitSystem.metric,
    ) -> dict[str, object]:
        return await day_weather(
            category=WeatherCategory.historical,
            weather_date=weather_date,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            units=units,
            client=client,
        )

    @application.get(
        "/api/v1/weather/historical/month/{year}/{month}",
        response_model=MonthlyWeatherResponse,
        tags=["weather"],
        summary="Retrieve daily high and low temperatures for one historical month",
    )
    async def historical_weather_for_month(
        year: Annotated[int, Path(ge=1940, le=2100)],
        month: Annotated[int, Path(ge=1, le=12)],
        client: OpenMeteoClientDependency,
        latitude: Annotated[float, Query(ge=-90, le=90, examples=[41.8781])],
        longitude: Annotated[float, Query(ge=-180, le=180, examples=[-87.6298])],
        timezone: Annotated[str, Query(min_length=1, max_length=100)] = "auto",
        units: UnitSystem = UnitSystem.metric,
    ) -> dict[str, object]:
        month_start = date(year, month, 1)
        today = datetime.now(datetime_timezone.utc).date()
        if month_start >= date(today.year, today.month, 1):
            raise HTTPException(
                status_code=422, detail="Choose a month that has already ended."
            )
        try:
            payload = await client.get_historical_weather_for_month(
                month_start=month_start,
                month_end=date(year, month, monthrange(year, month)[1]),
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                units=units,
            )
        except OpenMeteoRequestError as exc:
            raise HTTPException(
                status_code=422,
                detail="Open-Meteo rejected the month or request parameters",
            ) from exc
        except OpenMeteoTimeoutError as exc:
            raise HTTPException(status_code=504, detail="Open-Meteo timed out") from exc
        except OpenMeteoResponseError as exc:
            raise HTTPException(
                status_code=502, detail="Open-Meteo returned an invalid response"
            ) from exc
        return {**payload, "category": WeatherCategory.historical}

    return application


app = create_app()
