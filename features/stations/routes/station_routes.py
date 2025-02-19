from typing import Dict
from fastapi import APIRouter, Depends, Request
from features.stations.models.summary_types import ConditionSummaryResponse
from features.waves.models.ndbc_types import NDBCStation
from features.stations.services.station_service import StationService
from features.stations.services.condition_summary_service import ConditionSummaryService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/stations",
    tags=["Stations"]
)

def get_service(request: Request) -> StationService:
    """Dependency to get the StationService instance."""
    return request.app.state.station_service

def get_condition_service(request: Request) -> ConditionSummaryService:
    """Dependency to get the ConditionSummaryService instance."""
    return request.app.state.condition_summary_service

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
    response_model=ConditionSummaryResponse,
    summary="Get station condition summary",
    description="Returns a human-readable summary of current conditions and trends over the next 6 hours"
)
async def get_station_conditions(
    station_id: str,
    service: ConditionSummaryService = Depends(get_condition_service)
):
    """Get a human-readable summary of conditions for a specific station."""
    return await service.get_station_condition_summary(station_id) 