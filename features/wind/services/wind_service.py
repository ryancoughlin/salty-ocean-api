from typing import Annotated
from fastapi import Depends, HTTPException

from features.wind.models.wind_types import WindForecastResponse
from features.wind.services.gfs_wind_client import GFSWindClient
from features.stations.services.station_service import StationService
from core.cache import cached
import logging

logger = logging.getLogger(__name__)

class WindService:
    def __init__(
        self,
        gfs_client: GFSWindClient,
        station_service: StationService
    ):
        self.gfs_client = gfs_client
        self.station_service = station_service

    @cached(
        namespace="wind_forecast",
        expire=14400  # 4 hours (max time between model runs)
    )
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