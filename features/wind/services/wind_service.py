import json
import logging
from typing import Dict, List
from fastapi import HTTPException

from features.wind.models.wind_types import WindData, WindForecast
from features.weather.services.gfs_service import GFSForecastManager
from features.stations.services.station_service import StationService
from core.cache import cached

logger = logging.getLogger(__name__)

class WindService:
    def __init__(self, gfs_manager: GFSForecastManager, station_service: StationService):
        self.gfs_manager = gfs_manager
        self.station_service = station_service

    @cached(namespace="wind_stations", expire=None)
    async def get_stations(self) -> List[Dict]:
        """Get all wind stations."""
        try:
            return self.station_service.get_all_stations()
        except Exception as e:
            logger.error(f"Error getting stations: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="wind_stations", expire=None)
    async def get_stations_geojson(self) -> Dict:
        """Get stations in GeoJSON format for mapping."""
        try:
            stations = self.station_service.get_all_stations()
            
            return {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [station["location"]["coordinates"][0], station["location"]["coordinates"][1]]
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
            logger.error(f"Error creating GeoJSON response: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="wind_data")
    async def get_station_wind_data(self, station_id: str) -> WindData:
        """Get current wind observations for a specific station."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
            return self.gfs_manager.get_station_wind_data(station_id, station)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting wind data for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind data: {str(e)}"
            )

    @cached(namespace="wind_forecast")
    async def get_station_wind_forecast(self, station_id: str) -> WindForecast:
        """Get wind forecast for a specific station."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
            return self.gfs_manager.get_station_wind_forecast(station_id, station)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind forecast: {str(e)}"
            ) 