"""POST /api/v1/search: the natural-language search endpoint."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.search.geocode import Geocoder, PlaceNotFoundError
from app.search.schemas import SearchRequest, SearchResponse
from app.search.service import run_search


router = APIRouter(prefix="/api/v1", tags=["search"])


def get_geocoder(request: Request) -> Geocoder:
    return request.app.state.search_geocoder


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Turn a natural-language weather question into a view or a ranked list of cities",
)
async def search(request: SearchRequest,
                 geocoder: Annotated[Geocoder, Depends(get_geocoder)]) -> SearchResponse:
    today = request.today or datetime.now(timezone.utc).date()
    try:
        return await run_search(request.query, request.units, today, geocoder)
    except PlaceNotFoundError as exc:
        detail = exc.hint or f"Couldn't find a US place called “{exc.place}”."
        raise HTTPException(status_code=422, detail=detail) from exc