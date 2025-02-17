from fastapi import APIRouter, Depends, Request
from models.wind_types import WindData, WindForecast
from controllers.wind_controller import WindController

router = APIRouter()

def get_controller(request: Request) -> WindController:
    """Dependency to get the WindController instance."""
    return request.app.state.wind_controller

@router.get(
    "/stations",
    response_model=list[dict],
    summary="Get all wind stations",
    description="Returns a list of all available wind stations"
)
async def get_stations(
    controller: WindController = Depends(get_controller)
):
    """Get all wind stations."""
    return await controller.get_stations()

@router.get(
    "/stations/geojson",
    response_model=dict,
    summary="Get all wind stations in GeoJSON format",
    description="Returns all wind stations in GeoJSON format for mapping"
)
async def get_stations_geojson(
    controller: WindController = Depends(get_controller)
):
    """Get all wind stations in GeoJSON format."""
    return await controller.get_stations_geojson()

@router.get(
    "/{station_id}/wind",
    response_model=WindData,
    summary="Get current wind data for a station",
    description="Returns the current wind conditions from GFS for the specified station"
)
async def get_station_wind(
    station_id: str,
    controller: WindController = Depends(get_controller)
):
    """Get current wind data for a specific station."""
    return await controller.get_station_wind_data(station_id)

@router.get(
    "/{station_id}/wind/forecast",
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