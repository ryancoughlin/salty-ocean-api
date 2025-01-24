from typing import Dict, List
from datetime import datetime
from fastapi import APIRouter, HTTPException
from services.tide_service import TideService

router = APIRouter(prefix="/tide-stations", tags=["tide-stations"])
tide_service = TideService()

@router.get("")
async def get_all_stations() -> List[Dict]:
    """Get all tide stations"""
    try:
        stations = tide_service.get_stations()
        return stations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/geojson")
async def get_stations_geojson() -> Dict:
    """Get stations in GeoJSON format for mapping"""
    try:
        stations = tide_service.get_stations()
        
        geojson = {
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
        return geojson
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{station_id}")
async def get_station_predictions(station_id: str, date: datetime = None) -> Dict:
    """
    Get predictions for a specific station
    Args:
        station_id: Station identifier
        date: Optional date for predictions (defaults to today)
    """
    try:
        # First verify station exists
        stations = tide_service.get_stations()
        station = next((s for s in stations if s["id"] == station_id), None)
        
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
            
        predictions = tide_service.get_predictions(station_id, date)
        
        return {
            "id": station_id,
            "name": station["name"],
            "predictions": [
                {
                    "time": p["t"],
                    "height": float(p["v"])
                }
                for p in predictions
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 