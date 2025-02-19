import logging
from typing import Dict, List
from fastapi import HTTPException

from features.wind.models.wind_types import WindData, WindForecastResponse
from features.wind.services.gfs_wind_client import GFSWindClient
from features.stations.services.station_service import StationService
from features.common.models.station_types import Station, Location
from core.cache import cached

logger = logging.getLogger(__name__)

class WindService:
    def __init__(
        self,
        gfs_client: GFSWindClient,
        station_service: StationService
    ):
        self.gfs_client = gfs_client
        self.station_service = station_service

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
            
            wind_data = await self.gfs_client.get_station_wind_data(station)
            if not wind_data:
                raise HTTPException(
                    status_code=503,
                    detail="Unable to fetch wind data"
                )
                
            return wind_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting wind data for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind data: {str(e)}"
            )

    @cached(namespace="wind_forecast")
    async def get_station_wind_forecast(self, station_id: str) -> WindForecastResponse:
        """Get wind forecast for a specific station."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
            
            forecast = await self.gfs_client.get_station_wind_forecast(station)
            if not forecast:
                raise HTTPException(
                    status_code=503,
                    detail="Unable to fetch wind forecast"
                )
                
            return forecast
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind forecast: {str(e)}"
            ) 