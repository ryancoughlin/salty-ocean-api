import json
import logging
from typing import Dict
from fastapi import HTTPException
from services.weather.gfs_service import GFSForecastManager
from models.wind_types import WindData, WindForecast
from core.cache import cached
from services.station_service import StationService

logger = logging.getLogger(__name__)

class WindController:
    def __init__(self, gfs_manager: GFSForecastManager, station_service: StationService):
        self.gfs_manager = gfs_manager
        self.station_service = station_service

    def _load_stations(self):
        """Load NDBC stations from JSON file."""
        try:
            stations_file = "ndbcStations.json"
            with open(stations_file) as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading station data: {str(e)}"
            )

    def _get_station(self, station_id: str) -> Dict:
        """Get station by ID."""
        stations = self._load_stations()
        station = next(
            (s for s in stations if s["id"] == station_id),
            None
        )
        
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found"
            )
        return station

    @cached(namespace="wind_data")
    async def get_station_wind_data(self, station_id: str) -> WindData:
        """Get current wind conditions for a specific station."""
        try:
            station = self.station_service.get_station(station_id)
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
            return self.gfs_manager.get_station_wind_forecast(station_id, station)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind forecast: {str(e)}"
            ) 