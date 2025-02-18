from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from features.tides.models.tide_types import (
    TideStation,
    TideStationPredictions,
    GeoJSONResponse
)
from features.tides.services.tide_service import TideService

router = APIRouter(
    prefix="/tides",
    tags=["Tides"]
)

def get_service(request: Request) -> TideService:
    """Dependency to get the TideService instance."""
    return request.app.state.tide_service

@router.get(
    "/stations",
    response_model=List[TideStation],
    summary="Get all tide stations",
    description="Returns a list of all available tide stations"
)
async def get_all_stations(
    service: TideService = Depends(get_service)
) -> List[TideStation]:
    """Get all tide stations."""
    return await service.get_all_stations()

@router.get(
    "/stations/geojson",
    response_model=GeoJSONResponse,
    summary="Get stations in GeoJSON format",
    description="Returns tide stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    service: TideService = Depends(get_service)
) -> GeoJSONResponse:
    """Get stations in GeoJSON format."""
    return await service.get_stations_geojson()

@router.get(
    "/stations/{station_id}/predictions",
    response_model=TideStationPredictions,
    summary="Get tide predictions for a station",
    description="Returns tide predictions for the specified station"
)
async def get_station_predictions(
    station_id: str,
    date: datetime = None,
    service: TideService = Depends(get_service)
) -> TideStationPredictions:
    """Get tide predictions for a specific station."""
    return await service.get_station_predictions(station_id, date) 