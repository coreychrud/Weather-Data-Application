"""Try natural-language search from the command line.

    python -m app.search.cli "sunny cities in July"
    python -m app.search.cli "weather in Boise tomorrow" --units metric
"""

import argparse
import asyncio
from datetime import date

import httpx

from app.models import UnitSystem
from app.search.geocode import Geocoder, PlaceNotFoundError, map_metros
from app.search.service import run_search


async def main() -> None:
    parser = argparse.ArgumentParser(description="Try natural-language weather search.")
    parser.add_argument("question")
    parser.add_argument("--units", choices=[u.value for u in UnitSystem], default="imperial")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=10) as http_client:
        geocoder = Geocoder(http_client, metros=map_metros())
        try:
            response = await run_search(args.question, UnitSystem(args.units), date.today(), geocoder)
        except PlaceNotFoundError as exc:
            raise SystemExit(exc.hint or f"Couldn't find a US place called {exc.place!r}.")

    print(response.summary, "\n")
    print(response.model_dump_json(indent=2, exclude_defaults=True))


if __name__ == "__main__":
    asyncio.run(main())