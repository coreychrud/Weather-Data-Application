"""Answer a question: parse it, resolve places or rank cities, and summarize.

The search endpoint doesn't fetch weather itself. For lookups it tells the
frontend which view, places and date to show, and the views fetch their own
data as they already do. For discover searches the answer comes from the
climate table, so no API calls are needed at all.
"""

import asyncio
import re
from datetime import date

from app.models import UnitSystem
from app.search.geocode import Geocoder
from app.search.intent import SearchMode, normalize_intent
from app.search.ranking import rank_cities
from app.search.rules import parse_rules
from app.search.schemas import DiscoverResult, SearchLocation, SearchResponse
from app.search.states import STATES, state_name
from app.search.summary import depth, describe_lookup, highlight, summarize_discover, temperature


async def run_search(query: str, units: UnitSystem, today: date,
                     geocoder: Geocoder) -> SearchResponse:
    intent = normalize_intent(parse_rules(query, today), today)
    units = intent.units or units
    base = {"query": query, "mode": intent.mode, "units": units}

    if intent.mode is SearchMode.discover:
        ranking = rank_cities(intent.condition, intent.months, intent.region, intent.limit)
        results = [
            DiscoverResult(
                rank=rank, id=city.id, name=city.name, region=city.region,
                latitude=city.latitude, longitude=city.longitude,
                highlight=highlight(city, intent.condition, units),
                good_months=city.good_months, month_count=len(ranking.months),
                high=temperature(city.averages["high_c"], units),
                low=temperature(city.averages["low_c"], units),
                sun_hours=city.averages["sun_hours"], rainy_days=city.averages["rainy_days"],
                precipitation=depth(city.averages["precip_mm"], units),
                snowfall=depth((city.averages["snow_cm"] or 0) * 10, units),
            )
            for rank, city in enumerate(ranking.cities, start=1)
        ]
        return SearchResponse(
            **base, condition=intent.condition, months=intent.months,
            region=_code(intent.region), results=results,
            locations=[SearchLocation(**r.model_dump(include=set(SearchLocation.model_fields)))
                       for r in results[:3]],          # the map shows up to 3
            summary=summarize_discover(ranking, intent.condition, units),
        )

    if intent.mode is SearchMode.heatmap:
        state = next((state_name(p) for p in intent.places if state_name(p)), None)
        return SearchResponse(**base, date=intent.date, metric=intent.metric,
                              region=_code(state), summary=describe_lookup(intent, [], state))

    if place_only(query, intent):
        return SearchResponse(**base, place_only=True, place_query=intent.places[0],
                              summary=f"Choose the {intent.places[0]} you mean.")
    # current, forecast, historical, monthly: resolve the places (up to 3) at once.
    
    places = await asyncio.gather(*(geocoder.resolve(name) for name in intent.places))
    locations = [SearchLocation(id=p.id, name=p.name, region=p.region,
                                latitude=p.latitude, longitude=p.longitude) for p in places]
    summary = describe_lookup(intent, [f"{p.name}, {p.region}" if p.region else p.name
                                       for p in places], None)
    if not locations:
        summary += " Pick a location on the map, or name one in your search."
    return SearchResponse(
        **base, date=intent.date, month=intent.month, forecast_days=intent.forecast_days,
        locations=locations, needs_location=not locations, summary=summary,
    )


# Words that don't change what a place-name search means.
FILLER_WORDS = {
    "weather", "in", "for", "at", "of", "the", "show", "me", "find", "search", "what",
    "what's", "whats", "is", "how", "how's", "it", "like", "city", "town", "please",
    "conditions", "temperature", "temperatures", "temp",
}


def place_only(query: str, intent) -> bool:
    """Is the query just one place name, possibly wrapped in filler words?

    "Austin", "Austin, TX" and "weather in Springfield" are; "Austin tomorrow",
    "is it sunny in Austin" and "current weather in Austin" are not. A state on
    its own isn't either, since that resolves to the state's largest metro.
    """
    if intent.mode is not SearchMode.current or len(intent.places) != 1 or intent.units:
        return False
    place = intent.places[0]
    if state_name(place):
        return False
    rest = query.lower().replace("’", "'").replace(place.lower(), " ")
    words = re.findall(r"[a-z']+", rest)
    return all(word in FILLER_WORDS for word in words)

def _code(state: str | None) -> str | None:
    if not state:
        return None
    return next((code for code, name in STATES.items() if name == state_name(state)), None)