from typing import Dict
from fastapi import APIRouter, Depends, Request
from features.stations.models.station_types import (
    NDBCStation,
    NDBCForecastResponse,
    StationSummary
)
from features.waves.services.wave_service import WaveService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/waves",
    tags=["Waves"]
)

def get_service(request: Request) -> WaveService:
    """Dependency to get the WaveService instance."""
    return request.app.state.wave_service

@router.get(
    "/stations/geojson",
    summary="Get all wave stations in GeoJSON format",
    description="Returns all wave monitoring stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    service: WaveService = Depends(get_service)
):
    """Get all wave stations in GeoJSON format."""
    return await service.get_stations_geojson()

@router.get(
    "/stations/{station_id}/forecast",
    response_model=NDBCForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)
async def get_station_wave_forecast(
    station_id: str,
    service: WaveService = Depends(get_service)
):
    """Get wave model forecast for a specific station"""
    return await service.get_station_forecast(station_id)

@router.get(
    "/stations/{station_id}/summary",
    response_model=StationSummary,
    summary="Get wave conditions summary for a station",
    description="Returns a summary of wave conditions and forecast for the specified station"
)
async def get_station_wave_summary(
    station_id: str,
    service: WaveService = Depends(get_service)
):
    """Get a wave conditions summary for a specific station."""
    return await service.get_station_wave_summary(station_id) 