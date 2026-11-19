"""Request and response shapes for POST /api/v1/search."""

import datetime

from pydantic import BaseModel, Field

from app.models import UnitSystem
from app.search.intent import Condition, HeatmapMetric, SearchMode


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300, examples=["sunny cities in July"])
    units: UnitSystem = UnitSystem.imperial
    # The user's local date, so "tomorrow" means their tomorrow, not the server's.
    today: datetime.date | None = None


class SearchLocation(BaseModel):
    """Matches the frontend's location objects (name + two-letter region)."""

    id: str | None = None          # the map marker's id, for the 30 metros
    name: str
    region: str | None = None
    latitude: float
    longitude: float


class DiscoverResult(SearchLocation):
    rank: int
    highlight: str                 # e.g. "11.4 hours of sun a day"
    good_months: int
    month_count: int
    high: str
    low: str
    sun_hours: float | None
    rainy_days: float | None
    precipitation: str             # per month
    snowfall: str                  # per month


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    units: UnitSystem
    # Lookups
    date: datetime.date | None = None
    month: str | None = None
    forecast_days: int | None = None
    metric: HeatmapMetric | None = None
    locations: list[SearchLocation] = []
    needs_location: bool = False
    place_only: bool = False
    place_query: str | None = None
    # Heatmap and discover: two-letter state code, if the question named a state
    region: str | None = None
    # Discover
    condition: Condition | None = None
    months: list[int] = []
    results: list[DiscoverResult] = []
    summary: str