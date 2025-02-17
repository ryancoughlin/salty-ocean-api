from typing import List, Dict
from fastapi import APIRouter, Depends, Request
from models.ndbc_types import NDBCStation, NDBCForecastResponse
from controllers.wave_controller import WaveController
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/stations",
    tags=["Stations"]
)

def get_controller(request: Request) -> WaveController:
    """Dependency to get the WaveController instance."""
    return request.app.state.wave_controller

@router.get(
    "/geojson",
    summary="Get all stations in GeoJSON format",
    description="Returns all monitoring stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    controller: WaveController = Depends(get_controller)
):
    """Get all stations in GeoJSON format."""
    return await controller.get_stations_geojson()

@router.get(
    "/{station_id}/observations",
    response_model=NDBCStation,
    summary="Get current station observations",
    description="Returns the latest observations from NDBC for the specified station including waves, wind, and meteorological data"
)
async def get_station_observations(
    station_id: str,
    controller: WaveController = Depends(get_controller)
):
    """Get current observations for a specific station."""
    return await controller.get_station_observations(station_id)

@router.get(
    "/{station_id}/waves/forecast",
    response_model=NDBCForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)
async def get_station_wave_forecast(
    station_id: str,
    controller: WaveController = Depends(get_controller)
):
    """Get wave model forecast for a specific station"""
    return await controller.get_station_forecast(station_id)

@router.get(
    "/{station_id}/waves/summary",
    summary="Get wave conditions summary for a station",
    description="Returns a summary of wave conditions and forecast for the specified station"
)
async def get_station_wave_summary(
    station_id: str,
    controller: WaveController = Depends(get_controller)
):
    """Get a wave conditions summary for a specific station."""
    return await controller.get_station_wave_summary(station_id) 