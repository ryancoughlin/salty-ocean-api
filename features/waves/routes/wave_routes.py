from typing import Dict, Optional
from fastapi import APIRouter, Depends, Request

from features.waves.models.wave_types import WaveForecastResponse
from features.waves.services.wave_data_service import WaveDataService
from core.cache import cached
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/waves",
    tags=["Waves"]
)

def get_service(request: Request) -> WaveDataService:
    """Dependency to get the WaveService instance."""
    return request.app.state.wave_service

def wave_cache_key_builder(
    func,
    namespace: Optional[str] = "",
    station_id: str = "",
    *args,
    **kwargs,
):
    """Build a cache key that includes the station ID."""
    return f"{namespace}:{station_id}"

@router.get(
    "/geojson",
    summary="Get all wave stations in GeoJSON format",
    description="Returns all wave monitoring stations in GeoJSON format for mapping"
)
@cached(
    namespace="geojson",
    expire=None  # Static data, no expiration needed
)
async def get_stations_geojson(
    service: WaveDataService = Depends(get_service)
):
    """Get all wave stations in GeoJSON format."""
    return await service.get_stations_geojson()

@router.get(
    "/{station_id}/forecast",
    response_model=WaveForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)
@cached(
    namespace="wave_forecast",
    expire=14400,  # 4 hours (max time between model runs)
    key_builder=wave_cache_key_builder
)
async def get_station_wave_forecast(
    station_id: str,
    service: WaveDataService = Depends(get_service)
):
    """Get wave model forecast for a specific station"""
    return await service.get_station_forecast(station_id)
