from datetime import date

import pytest

from app.models import UnitSystem
from app.search.dates import find_date
from app.search.intent import Condition, HeatmapMetric, SearchIntent, SearchMode, normalize_intent
from app.search.rules import parse_rules


TODAY = date(2026, 11, 18)  # a Wednesday


def parsed(query: str) -> SearchIntent:
    return normalize_intent(parse_rules(query, TODAY), TODAY)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("on 2021-02-15", {"date": date(2021, 2, 15)}),
        ("on 12/25/2015", {"date": date(2015, 12, 25)}),
        ("christmas 2020", {"date": date(2020, 12, 25)}),
        ("march 3rd 1998", {"date": date(1998, 3, 3)}),
        ("yesterday", {"date": date(2026, 11, 17)}),
        ("the day after tomorrow", {"date": date(2026, 11, 20)}),
        ("3 days ago", {"date": date(2026, 11, 15)}),
        ("three days from now", {"date": date(2026, 11, 21)}),
        ("last tuesday", {"date": date(2026, 11, 17)}),
        ("this weekend", {"date": date(2026, 11, 21)}),
        ("last july", {"month": "2026-07"}),
        ("in january 2019", {"month": "2019-01"}),
        ("last month", {"month": "2026-10"}),
        ("next 5 days", {"forecast_days": 5}),
    ],
)
def test_find_date(phrase: str, expected: dict) -> None:
    found = find_date(phrase, TODAY)
    assert found is not None
    for field, value in expected.items():
        assert getattr(found, field) == value


def test_find_date_ignores_may_as_a_verb() -> None:
    assert find_date("it may rain", TODAY) is None


@pytest.mark.parametrize(
    ("query", "mode", "places", "day", "month"),
    [
        ("rain in Chicago last July", "monthly", ["Chicago"], None, "2026-07"),
        ("Seattle forecast for Friday", "forecast", ["Seattle"], date(2026, 11, 20), None),
        ("What's the weather in Austin, TX right now?", "current", ["Austin, TX"], None, None),
        ("how cold was it in Boston on Christmas 2020", "historical", ["Boston"], date(2020, 12, 25), None),
        ("Chicago weather", "current", ["Chicago"], None, None),
        ("Portland, OR in May 2024", "monthly", ["Portland, OR"], None, "2024-05"),
        ("Boise tomorrow", "forecast", ["Boise"], date(2026, 11, 19), None),
        ("is it sunny in Seattle", "current", ["Seattle"], None, None),
        ("what will the weather be on saturday", "forecast", [], date(2026, 11, 21), None),
    ],
)
def test_lookup_questions(query, mode, places, day, month) -> None:
    intent = parsed(query)
    assert intent.mode.value == mode
    assert intent.places == places
    assert intent.date == day
    assert intent.month == month


def test_comparisons_units_and_days() -> None:
    intent = parsed("compare Houston and Dallas next 5 days in celsius")
    assert intent.places == ["Houston", "Dallas"]
    assert intent.forecast_days == 5
    assert intent.units is UnitSystem.metric


def test_heatmaps() -> None:
    national = parsed("precipitation across the US yesterday")
    assert national.mode is SearchMode.heatmap
    assert national.metric is HeatmapMetric.precipitation
    assert national.places == []
    assert parsed("heatmap of Texas on 2021-02-15").places == ["Texas"]


@pytest.mark.parametrize(
    ("query", "condition", "months", "region", "limit"),
    [
        ("give me somewhere sunny for most of the year", Condition.sunny, [], None, 5),
        ("sunny cities in july", Condition.sunny, [7], None, 5),
        ("warmest places in Florida in winter", Condition.warm, [1, 2, 12], "Florida", 5),
        ("top 3 driest cities June through August", Condition.dry, [6, 7, 8], None, 3),
        ("where is it snowy in December", Condition.snowy, [12], None, 5),
        ("coldest cities in Minnesota", Condition.cold, [], "Minnesota", 5),
        ("pleasant cities in may", Condition.mild, [5], None, 5),
    ],
)
def test_discover_questions(query, condition, months, region, limit) -> None:
    intent = parsed(query)
    assert intent.mode is SearchMode.discover
    assert intent.condition is condition
    assert intent.months == months
    assert intent.region == region
    assert intent.limit == limit
    assert intent.places == []