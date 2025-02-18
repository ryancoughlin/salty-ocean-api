from typing import Dict
from fastapi import APIRouter, Depends, Request
from features.stations.models.station_types import NDBCStation, StationSummary
from features.stations.services.station_service import StationService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/stations",
    tags=["Stations"]
)

def get_service(request: Request) -> StationService:
    """Dependency to get the StationService instance."""
    return request.app.state.station_service

@router.get(
    "/geojson",
    summary="Get all stations in GeoJSON format",
    description="Returns all monitoring stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    service: StationService = Depends(get_service)
):
    """Get all stations in GeoJSON format."""
    return await service.get_stations_geojson()

@router.get(
    "/{station_id}/observations",
    response_model=NDBCStation,
    summary="Get current station observations",
    description="Returns the latest observations from NDBC for the specified station including waves, wind, and meteorological data"
)
async def get_station_observations(
    station_id: str,
    service: StationService = Depends(get_service)
):
    """Get current observations for a specific station."""
    return await service.get_station_observations(station_id)

@router.get(
    "/{station_id}/summary",
    response_model=StationSummary,
    summary="Get station summary",
    description="Returns a summary of the station including metadata and latest conditions"
)
async def get_station_summary(
    station_id: str,
    service: StationService = Depends(get_service)
):
    """Get a summary for a specific station."""
    return await service.get_station_summary(station_id) 