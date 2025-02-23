from fastapi import APIRouter, Depends, Request

from features.waves.models.wave_types import WaveForecastResponse
from features.waves.services.wave_data_service import WaveDataService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/waves",
    tags=["Waves"]
)

def get_service(request: Request) -> WaveDataService:
    """Dependency to get the WaveService instance."""
    return request.app.state.wave_service

@router.get(
    "/{station_id}/forecast",
    response_model=WaveForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)

async def get_station_wave_forecast(
    station_id: str,
    service: WaveDataService = Depends(get_service)
):
    """Get wave model forecast for a specific station"""
    return await service.get_station_forecast(station_id)
