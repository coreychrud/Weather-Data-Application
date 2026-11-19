"""Plain-English descriptions and summaries, written from templates.

Lookups get a sentence saying what's being shown. The views themselves
display the numbers. Discover searches get a summary built from the
climate table, since that's the answer itself.
"""

from datetime import date

from app.models import UnitSystem
from app.search.intent import Condition, SearchIntent, SearchMode
from app.search.ranking import Ranking, RankedCity


MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
SEASON_NAMES = {(12, 1, 2): "winter", (3, 4, 5): "spring", (6, 7, 8): "summer",
                (9, 10, 11): "fall"}

# What a "good month" means, for all-year summaries. (imperial, metric)
GOOD_MONTH_TEXT = {
    Condition.sunny: ("at least 8 hours of sun a day",) * 2,
    Condition.hot: ("highs of 90°F or more", "highs of 32°C or more"),
    Condition.warm: ("highs of 75–91°F", "highs of 24–33°C"),
    Condition.mild: ("highs of 64–81°F", "highs of 18–27°C"),
    Condition.cool: ("highs of 50–68°F", "highs of 10–20°C"),
    Condition.cold: ("highs of 41°F or below", "highs of 5°C or below"),
    Condition.dry: ("6 or fewer rainy days",) * 2,
    Condition.rainy: ("12 or more rainy days",) * 2,
    Condition.snowy: ("4 or more inches of snow", "10 cm or more of snow"),
}


# --- Units -----------------------------------------------------------------

def temperature(celsius: float | None, units: UnitSystem) -> str:
    if celsius is None:
        return "unknown"
    if units is UnitSystem.imperial:
        return f"{round(celsius * 9 / 5 + 32)}°F"
    return f"{round(celsius)}°C"


def depth(millimeters: float | None, units: UnitSystem) -> str:
    if millimeters is None:
        return "unknown"
    if units is UnitSystem.imperial:
        return f"{millimeters / 25.4:.1f} in"
    return f"{round(millimeters)} mm"


def highlight(city: RankedCity, condition: Condition, units: UnitSystem) -> str:
    """The one number that explains a city's rank, e.g. '11.4 hours of sun a day'."""
    averages = city.averages
    if condition is Condition.sunny:
        return f"{averages['sun_hours']} hours of sun a day"
    if condition in (Condition.dry, Condition.rainy):
        return f"{round(averages['rainy_days'] or 0)} rainy days a month"
    if condition is Condition.snowy:
        return f"{depth((averages['snow_cm'] or 0) * 10, units)} of snow a month"
    return f"average high {temperature(averages['high_c'], units)}"


# --- Dates -----------------------------------------------------------------

def long_date(value: date) -> str:
    # strftime's %-d (day without a leading zero) doesn't work on Windows.
    return f"{value:%B} {value.day}, {value.year}"


def months_phrase(months: list[int]) -> str:
    if not months or len(months) == 12:
        return "year-round"
    if season := SEASON_NAMES.get(tuple(sorted(months, key=lambda m: (m - 12) % 12))):
        return f"in {season}"
    names = [MONTH_NAMES[m - 1] for m in months]
    return "in " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1])


def join_names(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])}, and {names[-1]}"


# --- Summaries -------------------------------------------------------------

def describe_lookup(intent: SearchIntent, place_names: list[str], state: str | None) -> str:
    if intent.mode is SearchMode.heatmap:
        what = ("daily total precipitation" if intent.metric and intent.metric.value == "precipitation"
                else "daily average temperature")
        return f"Showing {what} across {state or 'the US'} on {long_date(intent.date)}."

    where = join_names(place_names) or "your selected location"
    if intent.mode is SearchMode.current:
        return f"Showing current conditions in {where}."
    if intent.mode is SearchMode.forecast:
        if intent.date:
            return f"Showing the forecast for {where} on {intent.date:%A}, {long_date(intent.date)}."
        return f"Showing the {intent.forecast_days}-day forecast for {where}."
    if intent.mode is SearchMode.historical:
        return f"Showing the weather in {where} on {long_date(intent.date)}."
    year, month = (int(part) for part in intent.month.split("-"))
    return f"Showing daily highs and lows for {where} in {MONTH_NAMES[month - 1]} {year}."


def summarize_discover(ranking: Ranking, condition: Condition, units: UnitSystem) -> str:
    if not ranking.cities:
        return "There isn't enough climate data to answer that."
    when = months_phrase(ranking.months)
    top, rest = ranking.cities[0], ranking.cities[1:3]
    label = f"{top.name}, {top.region}"

    if len(ranking.months) == 12:
        bar = GOOD_MONTH_TEXT[condition][units is UnitSystem.metric]
        text = (f"{label} is the most consistent: {top.good_months} of 12 months have {bar} "
                f"({highlight(top, condition, units)} on average).")
    else:
        text = f"{label} has {ranking.description} {when} ({highlight(top, condition, units)})."
    if rest:
        others = [f"{c.name}, {c.region} ({highlight(c, condition, units)})" for c in rest]
        text += f" Next are {join_names(others)}."
    if ranking.note:
        text += f" {ranking.note}"
    return text