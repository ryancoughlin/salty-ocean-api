from fastapi import APIRouter, Depends, Request
from models.wind_types import WindData, WindForecast
from controllers.wind_controller import WindController

router = APIRouter()

def get_controller(request: Request) -> WindController:
    """Dependency to get the WindController instance."""
    return request.app.state.wind_controller

@router.get(
    "/{station_id}/current",
    response_model=WindData,
    summary="Get current wind conditions for a station",
    description="Returns the current wind conditions from GFS for the specified station"
)
async def get_station_wind_data(
    station_id: str,
    controller: WindController = Depends(get_controller)
):
    """Get current wind conditions for a specific station."""
    return await controller.get_station_wind_data(station_id)

@router.get(
    "/{station_id}/forecast",
    response_model=WindForecast,
    summary="Get wind forecast for a station",
    description="Returns a 7-day wind forecast at 3-hour intervals from GFS for the specified station"
)
async def get_station_wind_forecast(
    station_id: str,
    controller: WindController = Depends(get_controller)
):
    """Get wind forecast for a specific station."""
    return await controller.get_station_wind_forecast(station_id) 