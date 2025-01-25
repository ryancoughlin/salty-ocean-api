from fastapi import APIRouter
from typing import List, Optional
from datetime import datetime
from models.tide import (
    TideStation,
    TideStationPredictions,
    GeoJSONResponse
)
from controllers.tide_controller import TideController

router = APIRouter(tags=["tide-stations"])
controller = TideController()

@router.get(
    "",
    response_model=List[TideStation],
    summary="Get all tide stations",
    description="Returns a list of all tide stations"
)
async def get_stations() -> List[TideStation]:
    """Get all tide stations."""
    return controller.get_all_stations()

@router.get(
    "/geojson",
    response_model=GeoJSONResponse,
    summary="Get stations in GeoJSON format",
    description="Returns tide stations in GeoJSON format for mapping applications"
)
async def get_stations_geojson() -> GeoJSONResponse:
    """Get stations in GeoJSON format for mapping."""
    return controller.get_stations_geojson()

@router.get(
    "/{station_id}/predictions",
    response_model=TideStationPredictions,
    summary="Get tide predictions for a station",
    description="Returns high and low tide predictions for a station. By default, returns predictions for the next 7 days."
)
async def get_station_predictions(
    station_id: str,
    date: Optional[datetime] = None
) -> TideStationPredictions:
    """Get tide predictions for a specific station.
    
    Args:
        station_id: The NOAA station identifier
        date: Optional start date for predictions (defaults to today)
    
    Returns:
        TideStationPredictions: Station details and list of high/low tide predictions
    """
    return controller.get_station_predictions(station_id, date) 