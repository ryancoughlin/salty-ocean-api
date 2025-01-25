from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException
from models.tide import (
    TideStation,
    TideStationPredictions,
    GeoJSONResponse
)
from controllers.tide_controller import TideController

router = APIRouter(tags=["tide-stations"])
controller = TideController()

@router.get(
    "/",
    response_model=List[TideStation],
    summary="Get all tide stations",
    description="Returns a list of all available tide stations"
)
async def get_all_stations() -> List[TideStation]:
    """Get all tide stations."""
    return await controller.get_all_stations()

@router.get(
    "/geojson",
    response_model=GeoJSONResponse,
    summary="Get stations in GeoJSON format",
    description="Returns tide stations in GeoJSON format for mapping"
)
async def get_stations_geojson() -> GeoJSONResponse:
    """Get stations in GeoJSON format."""
    return await controller.get_stations_geojson()

@router.get(
    "/{station_id}/predictions",
    response_model=TideStationPredictions,
    summary="Get tide predictions for a station",
    description="Returns tide predictions for the specified station"
)
async def get_station_predictions(
    station_id: str,
    date: datetime = None
) -> TideStationPredictions:
    """Get tide predictions for a specific station."""
    return await controller.get_station_predictions(station_id, date) 