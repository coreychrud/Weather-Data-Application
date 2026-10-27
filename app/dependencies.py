from typing import Annotated

from fastapi import Depends, Request

from app.open_meteo import OpenMeteoClient


def get_open_meteo_client(request: Request) -> OpenMeteoClient:
    return request.app.state.open_meteo_client


OpenMeteoClientDependency = Annotated[
    OpenMeteoClient, Depends(get_open_meteo_client)
]

