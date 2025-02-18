from fastapi import APIRouter, Depends, Request
from features.wind.models.wind_types import WindData, WindForecastResponse
from features.wind.services.wind_service import WindService

router = APIRouter(
    prefix="/wind",
    tags=["Wind"]
)

def get_service(request: Request) -> WindService:
    """Dependency to get the WindService instance."""
    return request.app.state.wind_service

@router.get(
    "/{station_id}/current",
    response_model=WindData,
    summary="Get current wind data for a station",
    description="Returns the current wind conditions from GFS for the specified station"
)
async def get_station_wind(
    station_id: str,
    service: WindService = Depends(get_service)
):
    """Get current wind data for a specific station."""
    return await service.get_station_wind_data(station_id)

@router.get(
    "/{station_id}/forecast",
    response_model=WindForecastResponse,
    summary="Get wind forecast for a station",
    description="Returns a 7-day wind forecast at 3-hour intervals from GFS for the specified station"
)
async def get_station_wind_forecast(
    station_id: str,
    service: WindService = Depends(get_service)
):
    """Get wind forecast for a specific station."""
    return await service.get_station_wind_forecast(station_id) 