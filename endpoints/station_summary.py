from typing import Dict
from fastapi import APIRouter, Depends, Request
from models.ndbc_types import StationSummary
from controllers.station_controller import StationController
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/stations",
    tags=["Stations"]
)

def get_controller(request: Request) -> StationController:
    """Dependency to get the StationController instance."""
    return request.app.state.station_controller

@router.get(
    "/geojson",
    summary="Get all stations in GeoJSON format",
    description="Returns all monitoring stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    controller: StationController = Depends(get_controller)
):
    """Get all stations in GeoJSON format."""
    return await controller.get_stations_geojson()

@router.get(
    "/{station_id}/summary",
    response_model=StationSummary,
    summary="Get station summary",
    description="Returns a summary of the station including metadata and latest conditions"
)
async def get_station_summary(
    station_id: str,
    controller: StationController = Depends(get_controller)
):
    """Get a summary for a specific station."""
    return await controller.get_station_summary(station_id) 