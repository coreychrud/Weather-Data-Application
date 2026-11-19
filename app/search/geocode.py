"""Turn place names from a question into coordinates.

1. The 30 map metros, including common nicknames ("NYC", "Dallas", "DC").
   These resolve instantly, without a network call, and come back with the
   same id, name and region as the map's markers.
2. A state on its own ("weather in Texas") becomes that state's largest metro.
3. Anything else goes to the Open-Meteo Geocoding API, limited to the US.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.search.ranking import CLIMATE_FILE, load_climate
from app.search.states import STATES, state_name


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Nicknames and parts of multi-city metro names -> the metro's name in places.js.
METRO_ALIASES = {
    "nyc": "New York", "new york city": "New York", "manhattan": "New York",
    "la": "Los Angeles", "dallas": "Dallas–Fort Worth", "fort worth": "Dallas–Fort Worth",
    "dfw": "Dallas–Fort Worth", "dc": "Washington", "washington dc": "Washington",
    "riverside": "Riverside–San Bernardino", "san bernardino": "Riverside–San Bernardino",
    "inland empire": "Riverside–San Bernardino", "san francisco": "San Francisco Bay Area",
    "sf": "San Francisco Bay Area", "bay area": "San Francisco Bay Area",
    "oakland": "San Francisco Bay Area", "minneapolis": "Minneapolis–St. Paul",
    "st paul": "Minneapolis–St. Paul", "saint paul": "Minneapolis–St. Paul",
    "twin cities": "Minneapolis–St. Paul", "tampa": "Tampa Bay", "st petersburg": "Tampa Bay",
    "saint louis": "St. Louis", "philly": "Philadelphia", "vegas": "Las Vegas",
}


def map_metros() -> list[dict]:
    """The 30 metros from the climate table, or none if it hasn't been built yet."""
    return list(load_climate()) if CLIMATE_FILE.exists() else []


class PlaceNotFoundError(Exception):
    def __init__(self, place: str, hint: str = "") -> None:
        super().__init__(place)
        self.place = place
        self.hint = hint


@dataclass(frozen=True)
class Place:
    name: str
    region: str | None          # two-letter postal code, like the map uses
    latitude: float
    longitude: float
    id: str | None = None       # set when the place is one of the map's metros


def _key(text: str) -> str:
    """Normalize for matching: 'St. Louis' / 'st louis' / 'Dallas–Fort Worth'."""
    text = text.lower().replace("–", "-").replace(".", "")
    return " ".join(text.split())


class Geocoder:
    def __init__(self, http_client: httpx.AsyncClient, metros: list[dict]) -> None:
        """metros: rows with id, name, region, latitude, longitude, largest first."""
        self._http_client = http_client
        self._metros = [Place(m["name"], m["region"], m["latitude"], m["longitude"], m["id"])
                        for m in metros]
        self._by_name = {_key(metro.name): metro for metro in self._metros}
        for alias, name in METRO_ALIASES.items():
            if _key(name) in self._by_name:
                self._by_name.setdefault(alias, self._by_name[_key(name)])
        self._cache: dict[str, Place] = {}

    async def resolve(self, place: str) -> Place:
        key = _key(place)
        if key not in self._cache:
            self._cache[key] = await self._resolve(place.strip(), key)
        return self._cache[key]

    async def _resolve(self, original: str, key: str) -> Place:
        city, state = _split_state(key)

        # A state on its own: use its largest metro.
        if not city and state:
            for metro in self._metros:
                if metro.region == _code(state):
                    return metro
            raise PlaceNotFoundError(original, f"None of the map's metros are in {state}; "
                                               f"try a city in {state}.")

        metro = self._by_name.get(city)
        if metro and (state is None or metro.region == _code(state)):
            return metro

        found = await self._geocode(city, state)
        if found is None:
            raise PlaceNotFoundError(original)
        return found

    async def _geocode(self, city: str, state: str | None) -> Place | None:
        try:
            response = await self._http_client.get(GEOCODING_URL, params={
                "name": city, "count": 10, "language": "en", "format": "json",
                "countryCode": "US",
            })
            response.raise_for_status()
            results: list[dict[str, Any]] = response.json().get("results") or []
        except (httpx.HTTPError, ValueError):
            return None
        if state:
            # The API matches names only, so filter by state ourselves.
            results = [r for r in results if r.get("admin1") == state]
        if not results:
            return None
        best = results[0]
        admin1 = best.get("admin1")
        return Place(best["name"], _code(admin1) if admin1 else None,
                     float(best["latitude"]), float(best["longitude"]))


def _split_state(key: str) -> tuple[str, str | None]:
    """'austin, tx' -> ('austin', 'Texas'); 'texas' -> ('', 'Texas'); 'austin' -> ('austin', None)."""
    if state := state_name(key):
        # "washington" alone is the state; "washington dc" is handled as a metro alias.
        return "", state
    city, comma, rest = key.rpartition(",")
    if comma and (state := state_name(rest)):
        return city.strip(), state
    return key, None


def _code(state: str) -> str | None:
    return next((code for code, name in STATES.items() if name == state), None)