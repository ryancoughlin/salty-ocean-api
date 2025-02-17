from typing import List, Dict
from fastapi import APIRouter, Depends, Request
from models.ndbc_types import NDBCStation, NDBCForecastResponse
from controllers.offshore_controller import OffshoreController
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def get_controller(request: Request) -> OffshoreController:
    """Dependency to get the OffshoreController instance."""
    return request.app.state.offshore_controller

@router.get(
    "/stations/geojson",
    summary="Get all stations in GeoJSON format",
    description="Returns all NDBC stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    controller: OffshoreController = Depends(get_controller)
):
    """Get all NDBC stations in GeoJSON format."""
    return await controller.get_stations_geojson()

@router.get(
    "/{station_id}/wave",
    response_model=NDBCStation,
    summary="Get current wave conditions for a station",
    description="Returns the latest wave observations from NDBC for the specified station"
)
async def get_station_wave_data(
    station_id: str,
    controller: OffshoreController = Depends(get_controller)
):
    """Get current wave conditions for a specific NDBC station."""
    return await controller.get_station_observations(station_id)

@router.get(
    "/{station_id}/wave/forecast",
    response_model=NDBCForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)
async def get_station_wave_forecast(
    station_id: str,
    controller: OffshoreController = Depends(get_controller)
):
    """Get wave model forecast for a specific station"""
    return await controller.get_station_forecast(station_id)

@router.get(
    "/{station_id}/wave/summary",
    summary="Get wave conditions summary for a station",
    description="Returns a summary of wave conditions and forecast for the specified station"
)
async def get_station_wave_summary(
    station_id: str,
    controller: OffshoreController = Depends(get_controller)
):
    """Get a wave conditions summary for a specific station."""
    return await controller.get_station_summary(station_id) 