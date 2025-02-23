from typing import Dict, Optional
from fastapi import APIRouter, Depends, Request

from features.waves.models.wave_types import WaveForecastResponse
from features.waves.services.wave_data_service_v2 import WaveDataServiceV2

import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/waves/v2",
    tags=["Waves V2"]
)

def get_service(request: Request) -> WaveDataServiceV2:
    """Dependency to get the WaveService instance."""
    return request.app.state.wave_service_v2

@router.get(
    "/{station_id}/forecast",
    response_model=WaveForecastResponse,
    summary="Get wave forecast for a station using GRIB data",
    description="Returns the latest wave model forecast from NOAA GFS GRIB files for the specified station"
)
async def get_station_wave_forecast(
    station_id: str,
    service: WaveDataServiceV2 = Depends(get_service)
):
    """Get wave model forecast for a specific station using GRIB data"""
    response = await service.get_station_forecast(station_id)
    return response
