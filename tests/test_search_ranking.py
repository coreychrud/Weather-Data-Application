import json

import pytest

from app.search.intent import Condition
from app.search.ranking import CLIMATE_FILE, load_climate, rank_cities


def city(id_, name, region, *, high, sun=8.0, rainy=8.0, snow=0.0):
    """A fake climate-table row. Single numbers repeat for all 12 months."""
    def months(value):
        return list(value) if isinstance(value, (list, tuple)) else [value] * 12

    return {
        "id": id_, "name": name, "region": region, "latitude": 0.0, "longitude": 0.0,
        "high_c": months(high), "low_c": [h - 10 for h in months(high)],
        "sun_hours": months(sun), "rainy_days": months(rainy),
        "precip_mm": [r * 8 for r in months(rainy)], "snow_cm": months(snow),
    }


# Phoenix: hot and very sunny. Seattle: mild summers, grey and rainy otherwise.
# Miami: warm all year. Minneapolis: cold, snowy winters. Austin: hot Texas summers.
CLIMATE = (
    city("metro-1-phoenix", "Phoenix", "AZ", high=[19, 22, 25, 29, 34, 39, 41, 40, 37, 31, 24, 19],
         sun=[8, 9, 10, 11, 12, 13, 13, 12, 10, 9, 8, 8], rainy=2),
    city("metro-2-seattle", "Seattle", "WA", high=[8, 10, 12, 15, 19, 22, 26, 26, 22, 16, 11, 8],
         sun=[2, 3, 5, 7, 9, 10, 11, 10, 8, 5, 2, 2], rainy=[18, 15, 16, 13, 10, 7, 3, 4, 7, 13, 18, 18]),
    city("metro-3-miami", "Miami", "FL", high=[25, 26, 27, 28, 30, 31, 32, 32, 31, 29, 27, 26],
         sun=[7, 8, 8, 9, 8, 7, 8, 8, 7, 7, 7, 7], rainy=[5, 4, 5, 5, 9, 15, 15, 17, 16, 11, 6, 5]),
    city("metro-4-minneapolis-st-paul", "Minneapolis–St. Paul", "MN",
         high=[-6, -3, 4, 13, 20, 26, 28, 27, 22, 14, 5, -3], sun=[4, 5, 6, 7, 8, 9, 10, 9, 7, 5, 4, 3],
         snow=[25, 20, 15, 5, 0, 0, 0, 0, 0, 2, 15, 22]),
    city("metro-5-austin", "Austin", "TX", high=[17, 19, 23, 27, 31, 34, 36, 36, 33, 28, 22, 18], sun=8),
)


def names(ranking):
    return [c.name for c in ranking.cities]


def test_sunny_in_july() -> None:
    ranking = rank_cities(Condition.sunny, [7], climate=CLIMATE)
    assert names(ranking)[:2] == ["Phoenix", "Seattle"]   # Seattle summers really are sunny
    assert ranking.cities[0].averages["sun_hours"] == 13


def test_sunny_all_year_rewards_consistency() -> None:
    ranking = rank_cities(Condition.sunny, [], climate=CLIMATE)
    phoenix, *_ = ranking.cities
    assert phoenix.name == "Phoenix"
    assert phoenix.good_months == 12
    assert ranking.months == list(range(1, 13))
    # Seattle has some very sunny months but far fewer good ones, so it ranks low.
    assert names(ranking).index("Seattle") > names(ranking).index("Miami")


def test_mild_and_warm_use_closeness_to_a_target() -> None:
    assert names(rank_cities(Condition.warm, [1], climate=CLIMATE))[0] == "Miami"
    assert names(rank_cities(Condition.mild, [7], climate=CLIMATE))[0] == "Seattle"


def test_cold_snowy_dry_and_rainy() -> None:
    winter = [12, 1, 2]
    assert names(rank_cities(Condition.cold, winter, climate=CLIMATE))[0] == "Minneapolis–St. Paul"
    assert names(rank_cities(Condition.snowy, winter, climate=CLIMATE))[0] == "Minneapolis–St. Paul"
    assert names(rank_cities(Condition.dry, [], climate=CLIMATE))[0] == "Phoenix"
    assert names(rank_cities(Condition.rainy, winter, climate=CLIMATE))[0] == "Seattle"


def test_limit() -> None:
    assert len(rank_cities(Condition.hot, [7], limit=2, climate=CLIMATE).cities) == 2


def test_region_filter_and_notes() -> None:
    texas = rank_cities(Condition.hot, [7], region="Texas", climate=CLIMATE)
    assert names(texas) == ["Austin"]
    assert texas.note == "Only 1 of the 5 metros is in Texas."

    wyoming = rank_cities(Condition.hot, [7], region="Wyoming", climate=CLIMATE)
    assert len(wyoming.cities) == 5                       # falls back to every metro
    assert "None of the 5 metros are in Wyoming" in wyoming.note


def test_missing_months_are_skipped() -> None:
    patchy = city("metro-9-x", "Patchy", "CA", high=20, sun=[None] * 6 + [13] * 6)
    ranking = rank_cities(Condition.sunny, [1, 7], climate=CLIMATE + (patchy,))
    assert ranking.cities[0].name == "Patchy"             # scored on July alone
    assert ranking.cities[0].averages["sun_hours"] == 13


@pytest.mark.skipif(not CLIMATE_FILE.exists(), reason="climate table not built yet")
def test_the_real_climate_table() -> None:
    cities = load_climate()
    assert len(cities) == 30
    for row in cities:
        for field_name in ("high_c", "low_c", "sun_hours", "rainy_days", "precip_mm", "snow_cm"):
            assert len(row[field_name]) == 12
    ranking = rank_cities(Condition.sunny, [])
    assert len(ranking.cities) == 5