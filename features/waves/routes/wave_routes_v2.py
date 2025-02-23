from typing import Dict, Optional
from fastapi import APIRouter, Depends, Request

from features.waves.models.wave_types import WaveForecastResponse
from features.waves.services.wave_data_service_v2 import WaveDataServiceV2, wave_forecast_key_builder
from core.cache import cached

import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/waves/v2",
    tags=["Waves V2"]
)

def get_service(request: Request) -> WaveDataServiceV2:
    """Dependency to get the WaveServiceV2 instance."""
    return request.app.state.wave_service_v2

@router.get(
    "/{station_id}/forecast",
    response_model=WaveForecastResponse,
    summary="Get wave forecast for a station using GRIB data",
    description="Returns the latest wave model forecast from NOAA GFS GRIB files for the specified station"
)
@cached(
    namespace="wave_forecast",
    expire=14400,  # 4 hours (max time between model runs)
    key_builder=wave_forecast_key_builder
)
async def get_station_wave_forecast(
    station_id: str,
    service: WaveDataServiceV2 = Depends(get_service)
):
    """Get wave model forecast for a specific station using GRIB data"""
    logger.debug(f"Handling forecast request for station {station_id}")
    response = await service.get_station_forecast(station_id)
    logger.debug(f"Forecast response ready for station {station_id}")
    return response

@router.get(
    "/stations",
    response_model=Dict,
    summary="Get all wave monitoring stations",
    description="Returns all wave monitoring stations in GeoJSON format"
)
async def get_wave_stations(
    service: WaveDataServiceV2 = Depends(get_service)
):
    """Get all wave monitoring stations in GeoJSON format"""
    return await service.get_stations_geojson() 