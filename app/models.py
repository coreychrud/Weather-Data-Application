from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class UnitSystem(StrEnum):
    metric = "metric"
    imperial = "imperial"


class WeatherCategory(StrEnum):
    forecast = "forecast"
    historical = "historical"


class CurrentWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: str
    interval: int
    temperature_2m: float
    relative_humidity_2m: int
    apparent_temperature: float
    is_day: int
    precipitation: float
    weather_code: int
    wind_speed_10m: float


class HourlyWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[str]
    temperature_2m: list[float | None]
    precipitation_probability: list[int | None]
    weather_code: list[int | None]


class DailyWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[str]
    weather_code: list[int | None]
    temperature_2m_max: list[float | None]
    temperature_2m_min: list[float | None]
    precipitation_probability_max: list[int | None]
    sunrise: list[str]
    sunset: list[str]


class ForecastResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latitude: float
    longitude: float
    generationtime_ms: float
    utc_offset_seconds: int
    timezone: str
    timezone_abbreviation: str
    elevation: float
    current_units: dict[str, str]
    current: CurrentWeather
    hourly_units: dict[str, str]
    hourly: HourlyWeather
    daily_units: dict[str, str]
    daily: DailyWeather


class DayHourlyWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[str]
    temperature_2m: list[float | None]
    relative_humidity_2m: list[int | None]
    precipitation: list[float | None]
    weather_code: list[int | None]
    wind_speed_10m: list[float | None]


class DayDailyWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[str]
    weather_code: list[int | None]
    temperature_2m_max: list[float | None]
    temperature_2m_min: list[float | None]
    precipitation_sum: list[float | None]
    sunrise: list[str]
    sunset: list[str]
    wind_speed_10m_max: list[float | None]


class DayWeatherResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: WeatherCategory
    latitude: float
    longitude: float
    generationtime_ms: float
    utc_offset_seconds: int
    timezone: str
    timezone_abbreviation: str
    elevation: float
    hourly_units: dict[str, str]
    hourly: DayHourlyWeather
    daily_units: dict[str, str]
    daily: DayDailyWeather


class HealthResponse(BaseModel):
    status: str

