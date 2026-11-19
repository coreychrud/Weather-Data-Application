"""Rank the 30 metros for discover searches such as "sunny cities in July".

Everything comes from the pre-built climate table (city_climate.json), so
ranking is plain Python with no API calls.

How a city is scored:
1. Each condition looks at one measure from the table, e.g. sunshine hours
   for "sunny" or average high for "hot".
2. That measure is averaged over the months the user asked about.
3. Each month also counts as "good" if it clears the condition's threshold,
   e.g. at least 8 hours of sun a day.

Cities are sorted by the average. For all-year questions ("somewhere sunny
for most of the year") they're sorted by the number of good months first,
so a city that's reliably sunny beats one with a few extreme months.
"""

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
from typing import Callable

from app.search.intent import Condition
from app.search.states import STATES


CLIMATE_FILE = Path(__file__).parent / "data" / "city_climate.json"
ALL_MONTHS = list(range(1, 13))


@dataclass(frozen=True)
class Rule:
    """How one condition scores a month. Higher scores are better."""

    score: Callable[[dict, int], float | None]   # (city, month index 0-11) -> score
    good: Callable[[dict, int], bool]            # does this month count as good?
    description: str                             # used in summaries


def _value(field_name: str) -> Callable[[dict, int], float | None]:
    return lambda city, m: city[field_name][m]


def _closeness(field_name: str, target: float) -> Callable[[dict, int], float | None]:
    """Score how near a value is to a target: 0 is perfect, more negative is worse."""
    def score(city: dict, m: int) -> float | None:
        value = city[field_name][m]
        return None if value is None else -abs(value - target)
    return score


def _negative(field_name: str) -> Callable[[dict, int], float | None]:
    def score(city: dict, m: int) -> float | None:
        value = city[field_name][m]
        return None if value is None else -value
    return score


def _between(field_name: str, low: float, high: float) -> Callable[[dict, int], bool]:
    return lambda city, m: city[field_name][m] is not None and low <= city[field_name][m] <= high


# Thresholds are in the table's units: °C, hours, days, cm.
RULES: dict[Condition, Rule] = {
    Condition.sunny: Rule(_value("sun_hours"), _between("sun_hours", 8, 24),
                          "the most sunshine"),
    Condition.hot: Rule(_value("high_c"), _between("high_c", 32, 60),
                        "the highest temperatures"),
    Condition.warm: Rule(_closeness("high_c", 29), _between("high_c", 24, 33),
                         "highs closest to 84°F"),
    Condition.mild: Rule(_closeness("high_c", 23), _between("high_c", 18, 27),
                         "highs closest to 73°F"),
    Condition.cool: Rule(_closeness("high_c", 15), _between("high_c", 10, 20),
                         "highs closest to 59°F"),
    Condition.cold: Rule(_negative("high_c"), _between("high_c", -60, 5),
                         "the lowest temperatures"),
    Condition.dry: Rule(_negative("rainy_days"), _between("rainy_days", 0, 6),
                        "the fewest rainy days"),
    Condition.rainy: Rule(_value("rainy_days"), _between("rainy_days", 12, 31),
                          "the most rainy days"),
    Condition.snowy: Rule(_value("snow_cm"), _between("snow_cm", 10, 1000),
                          "the most snowfall"),
}


@dataclass
class RankedCity:
    id: str
    name: str
    region: str
    latitude: float
    longitude: float
    score: float
    good_months: int                 # months (of those asked about) that clear the threshold
    averages: dict[str, float | None] = field(default_factory=dict)  # over the months asked about


@dataclass
class Ranking:
    cities: list[RankedCity]
    months: list[int]
    note: str | None = None          # e.g. "Only 4 of the 30 metros are in Texas."
    description: str = ""


@lru_cache(maxsize=1)
def load_climate(path: Path = CLIMATE_FILE) -> tuple[dict, ...]:
    """The climate table's cities. Cached, so the file is read once per process."""
    return tuple(json.loads(path.read_text(encoding="utf-8"))["cities"])


def rank_cities(condition: Condition, months: list[int], region: str | None = None,
                limit: int = 5, climate: tuple[dict, ...] | None = None) -> Ranking:
    climate = load_climate() if climate is None else climate
    rule = RULES[condition]
    months = months or ALL_MONTHS
    month_indexes = [month - 1 for month in months]

    candidates, note = _filter_region(climate, region, limit)

    ranked: list[RankedCity] = []
    for city in candidates:
        scores = [score for m in month_indexes if (score := rule.score(city, m)) is not None]
        if not scores:
            continue  # no data for these months
        ranked.append(RankedCity(
            id=city["id"], name=city["name"], region=city["region"],
            latitude=city["latitude"], longitude=city["longitude"],
            score=round(sum(scores) / len(scores), 2),
            good_months=sum(rule.good(city, m) for m in month_indexes),
            averages=_averages(city, month_indexes),
        ))

    all_year = len(months) == 12
    ranked.sort(key=lambda c: (c.good_months, c.score) if all_year else (c.score, c.good_months),
                reverse=True)
    return Ranking(cities=ranked[:limit], months=months, note=note,
                   description=rule.description)


def _filter_region(climate, region: str | None, limit: int):
    if not region:
        return list(climate), None
    code = next((code for code, name in STATES.items() if name.lower() == region.lower()), None)
    in_region = [city for city in climate if city["region"] == code]
    if not in_region:
        return list(climate), (f"None of the {len(climate)} metros are in {region}, "
                               "so these are the best across all of them.")
    if len(in_region) < limit:
        count = len(in_region)
        return in_region, f"Only {count} of the {len(climate)} metros {'is' if count == 1 else 'are'} in {region}."
    return in_region, None


def _averages(city: dict, month_indexes: list[int]) -> dict[str, float | None]:
    """Each measure averaged over the months asked about, for display."""
    def mean(field_name: str) -> float | None:
        values = [city[field_name][m] for m in month_indexes if city[field_name][m] is not None]
        return round(sum(values) / len(values), 1) if values else None

    return {name: mean(name) for name in
            ("high_c", "low_c", "sun_hours", "rainy_days", "precip_mm", "snow_cm")}