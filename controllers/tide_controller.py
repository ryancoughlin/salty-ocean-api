from typing import Dict, List
from datetime import datetime
from fastapi import HTTPException
from services.tide_service import TideService
from models.tide import TideStation, TideStationPredictions, GeoJSONResponse
from core.cache import cached
import logging

logger = logging.getLogger(__name__)

class TideController:
    def __init__(self):
        self.tide_service = TideService()

    @cached(namespace="tide_stations", expire=None)
    async def get_all_stations(self) -> List[TideStation]:
        """Get all tide stations"""
        try:
            stations = self.tide_service.get_stations()
            return [
                TideStation(
                    id=station["station_id"],
                    name=station["name"],
                    location={"lat": station["lat"], "lng": station["lng"]}
                )
                for station in stations
            ]
        except Exception as e:
            logger.error(f"Error getting stations: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="tide_stations", expire=None)
    async def get_stations_geojson(self) -> GeoJSONResponse:
        """Get stations in GeoJSON format for mapping"""
        try:
            stations = self.tide_service.get_stations()
            
            return GeoJSONResponse(
                type="FeatureCollection",
                features=[
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [station["lng"], station["lat"]]
                        },
                        "properties": {
                            "id": station["station_id"],
                            "name": station["name"],
                            "type": station["type"]
                        }
                    }
                    for station in stations
                ]
            )
        except Exception as e:
            logger.error(f"Error creating GeoJSON response: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="tide_predictions")
    async def get_station_predictions(self, station_id: str, date: datetime = None) -> TideStationPredictions:
        """Get predictions for a specific station"""
        try:
            # First verify station exists
            stations = self.tide_service.get_stations()
            station = next((s for s in stations if s["station_id"] == station_id), None)
            
            if not station:
                raise HTTPException(status_code=404, detail="Station not found")
                
            predictions = self.tide_service.get_predictions(station_id, date)
            
            return TideStationPredictions(
                id=station_id,
                name=station["name"],
                predictions=[
                    {
                        "time": p["t"],
                        "height": float(p["v"])
                    }
                    for p in predictions
                ]
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting predictions for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e)) 