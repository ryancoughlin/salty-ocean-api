from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException
from models.buoy import NDBCStation, NDBCObservation, NDBCForecastResponse
from controllers.offshore_controller import OffshoreController
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
controller = OffshoreController()

@router.get(
    "/{station_id}/observations",
    response_model=NDBCStation,
    summary="Get real-time observations for a station",
    description="Returns the latest observations from NDBC for the specified station"
)
async def get_station_observations(
    station_id: str
) -> NDBCStation:
    """Get real-time observations for a specific NDBC station."""
    return await controller.get_station_observations(station_id)

@router.get(
    "/{station_id}/forecast",
    response_model=NDBCForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)
async def get_station_forecast(
    station_id: str
) -> NDBCForecastResponse:
    """Get wave model forecast for a specific station"""
    return await controller.get_station_forecast(station_id)

@router.get("/{station_id}/summary")
async def get_station_summary(station_id: str) -> Dict:
    """Get a summary for a specific station."""
    return await controller.get_station_summary(station_id)

@router.get(
    "/geojson",
    summary="Get all stations in GeoJSON format",
    description="Returns all NDBC stations in GeoJSON format for mapping"
)
async def get_stations_geojson() -> Dict:
    """Get all NDBC stations in GeoJSON format."""
    return await controller.get_stations_geojson() 