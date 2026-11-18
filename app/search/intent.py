"""The structured search request that every parser (LLM or rules) must produce."""

import datetime
from datetime import date, timedelta
from enum import StrEnum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import UnitSystem


MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
EARLIEST_DATE = date(1940, 1, 1)
FORECAST_HORIZON_DAYS = 15
DEFAULT_DISCOVER_LIMIT = 5


class SearchMode(StrEnum):
    current = "current"
    forecast = "forecast"
    historical = "historical"
    monthly = "monthly"
    heatmap = "heatmap"
    discover = "discover"  # rank many cities by climate, e.g. "sunny cities in July"


class HeatmapMetric(StrEnum):
    temperature = "temperature"
    precipitation = "precipitation"


class Condition(StrEnum):
    """What a discover search ranks cities by."""

    sunny = "sunny"
    warm = "warm"
    hot = "hot"
    mild = "mild"
    cool = "cool"
    cold = "cold"
    dry = "dry"
    rainy = "rainy"
    snowy = "snowy"


class SearchIntent(BaseModel):
    """What the user asked for, before place names are resolved to coordinates."""

    model_config = ConfigDict(extra="ignore")

    mode: SearchMode
    places: list[str] = Field(default_factory=list, max_length=3)
    date: datetime.date | None = None
    month: str | None = None
    forecast_days: int | None = Field(default=None, ge=1, le=16)
    units: UnitSystem | None = None
    metric: HeatmapMetric | None = None
    # Discover mode only.
    condition: Condition | None = None
    months: list[int] = Field(default_factory=list)  # 1-12; empty means all year
    region: str | None = None  # a state to search within, e.g. "Texas"
    limit: int | None = Field(default=None, ge=1, le=10)

    @field_validator("places", mode="before")
    @classmethod
    def clean_places(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return cleaned[:3]
        return value

    @field_validator("month", mode="before")
    @classmethod
    def check_month(cls, value: object) -> object:
        if value in (None, ""):
            return None
        if not isinstance(value, str) or not MONTH_PATTERN.match(value):
            raise ValueError("month must use YYYY-MM format")
        return value

    @field_validator("months", mode="before")
    @classmethod
    def clean_months(cls, value: object) -> object:
        if value in (None, ""):
            return []
        if isinstance(value, int):
            value = [value]
        if isinstance(value, list):
            months = sorted({int(item) for item in value})
            if any(not 1 <= item <= 12 for item in months):
                raise ValueError("months must be numbers from 1 to 12")
            return months
        return value

    @field_validator("date", "units", "metric", "forecast_days", "condition", "region",
                     "limit", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value in ("", "null", "none") else value


def normalize_intent(intent: SearchIntent, today: date) -> SearchIntent:
    """Fill defaults and move requests into a mode that can actually serve them."""
    data = intent.model_copy()

    # A condition with no specific place is a discover search, whatever the mode says.
    if data.mode is SearchMode.discover or (data.condition and not data.places
                                            and data.mode is not SearchMode.heatmap):
        return _normalize_discover(data)

    data.condition, data.months, data.region, data.limit = None, [], None, None
    latest_forecast = today + timedelta(days=FORECAST_HORIZON_DAYS)

    # Monthly requests (or any request that only has a month).
    if data.mode is SearchMode.monthly or (data.month and data.date is None
                                           and data.mode is not SearchMode.heatmap):
        current_month = today.replace(day=1)
        month_start = _month_start(data.month) if data.month else _previous_month(current_month)
        data.month = None
        if month_start == current_month:
            # This month isn't over, so show the latest archived day instead.
            data.mode = SearchMode.historical
            data.date = max(month_start, today - timedelta(days=1))
            return _normalize_point_modes(data, today, latest_forecast)
        if month_start > current_month:
            data.mode = SearchMode.forecast
            data.date = month_start if month_start <= latest_forecast else None
            return _normalize_point_modes(data, today, latest_forecast)
        data.mode = SearchMode.monthly
        data.month = f"{max(month_start, EARLIEST_DATE):%Y-%m}"
        data.date = None
        return data

    if data.mode is SearchMode.heatmap:
        target = data.date or today
        data.date = min(max(target, EARLIEST_DATE), latest_forecast)
        data.metric = data.metric or HeatmapMetric.temperature
        data.month = None
        return data

    data.month = None
    return _normalize_point_modes(data, today, latest_forecast)


def _normalize_discover(data: SearchIntent) -> SearchIntent:
    data.mode = SearchMode.discover
    data.condition = data.condition or Condition.mild
    # Parsers sometimes give a month as "2027-07" or a date; keep only the month number.
    if not data.months and data.month:
        data.months = [int(data.month[5:7])]
    if not data.months and data.date:
        data.months = [data.date.month]
    # "sunny cities in Texas": the state may arrive in places instead of region.
    if data.region is None and len(data.places) == 1:
        data.region = data.places[0]
    data.places = []
    data.limit = data.limit or DEFAULT_DISCOVER_LIMIT
    data.date = data.month = data.forecast_days = data.metric = None
    return data


def _normalize_point_modes(data: SearchIntent, today: date, latest_forecast: date) -> SearchIntent:
    """Current, forecast and historical: one location, at most one date."""
    if data.date is not None:
        if data.date < today:
            data.mode = SearchMode.historical
            data.date = max(data.date, EARLIEST_DATE)
        elif data.date == today and data.mode is not SearchMode.forecast:
            data.mode = SearchMode.current
            data.date = None
        else:
            data.mode = SearchMode.forecast
            data.date = min(data.date, latest_forecast)

    if data.mode is SearchMode.historical and data.date is None:
        data.date = today - timedelta(days=7)          # same default as the frontend
    if data.mode is SearchMode.forecast:
        # Fetch enough days to include the requested date.
        needed = (data.date - today).days + 1 if data.date else 1
        data.forecast_days = min(max(data.forecast_days or 7, needed), 16)
    else:
        data.forecast_days = None
    if data.mode is SearchMode.current:
        data.date = None
    return data


def _month_start(value: str) -> date:
    year, month = (int(part) for part in value.split("-"))
    return date(year, month, 1)


def _previous_month(month_start: date) -> date:
    return (month_start - timedelta(days=1)).replace(day=1)


