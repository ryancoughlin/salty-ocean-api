from fastapi import APIRouter, Depends, Request
from features.wind.models.wind_types import WindForecastResponse
from features.wind.services.wind_data_service import WindDataService

router = APIRouter(
    prefix="/wind",
    tags=["Wind"],
    responses={
        404: {"description": "Station not found"},
        503: {"description": "Forecast service unavailable"}
    }
)

def get_wind_service(request: Request) -> WindDataService:
    """Get WindDataService instance from app state."""
    return request.app.state.wind_service

@router.get(
    "/{station_id}/forecast",
    response_model=WindForecastResponse,
    summary="Get wind forecast for a station",
    description="Returns a 7-day wind forecast at 3-hour intervals from GFS for the specified station"
)
async def get_station_wind_forecast(
    station_id: str,
    wind_service: WindDataService = Depends(get_wind_service)
) -> WindForecastResponse:
    """Get wind forecast for a specific station."""
    return await wind_service.get_station_forecast(station_id)