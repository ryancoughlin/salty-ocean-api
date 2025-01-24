from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from models.tide import (
    TideStation,
    TidePrediction,
    TideStationPredictions,
    GeoJSONResponse
)
from services.tide_service import TideService

router = APIRouter()
tide_service = TideService()

@router.get(
    "/",
    response_model=List[TideStation],
    summary="Get all tide stations",
    description="Returns a list of all tide stations"
)
async def get_stations() -> List[TideStation]:
    """Get all tide stations."""
    try:
        return tide_service.get_stations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/geojson",
    response_model=GeoJSONResponse,
    summary="Get stations in GeoJSON format",
    description="Returns tide stations in GeoJSON format for mapping applications"
)
async def get_stations_geojson() -> GeoJSONResponse:
    """Get stations in GeoJSON format for mapping"""
    try:
        stations = tide_service.get_stations()
        
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [station["lng"], station["lat"]]
                    },
                    "properties": {
                        "id": station["id"],
                        "name": station["name"]
                    }
                }
                for station in stations
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/{station_id}/predictions",
    response_model=TideStationPredictions,
    summary="Get tide predictions for a station",
    description="Returns tide predictions for a specific station"
)
async def get_station_predictions(
    station_id: str,
    date: Optional[datetime] = None
) -> TideStationPredictions:
    """Get tide predictions for a specific station."""
    try:
        # First verify station exists
        stations = tide_service.get_stations()
        station = next((s for s in stations if s["id"] == station_id), None)
        
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
            
        predictions = tide_service.get_predictions(station_id, date)
        
        return TideStationPredictions(
            id=station_id,
            name=station["name"],
            predictions=[
                TidePrediction(
                    time=p["t"],
                    height=float(p["v"])
                )
                for p in predictions
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 