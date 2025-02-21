from typing import Annotated
from fastapi import Depends, HTTPException

from features.wind.models.wind_types import WindForecastResponse
from features.wind.services.gfs_wind_client import GFSWindClient
from features.stations.services.station_service import StationService
from core.cache import cached
import logging

logger = logging.getLogger(__name__)

async def get_wind_forecast(
    station_id: str,
    gfs_client: Annotated[GFSWindClient, Depends()],
    station_service: Annotated[StationService, Depends()]
) -> WindForecastResponse:
    """
    Get wind forecast for a specific station.
    
    Args:
        station_id: The ID of the station to get forecast for
        gfs_client: GFS client for fetching wind data
        station_service: Service for station operations
        
    Returns:
        WindForecastResponse containing the forecast data
        
    Raises:
        HTTPException: If station not found or forecast unavailable
    """
    station = station_service.get_station(station_id)
    if not station:
        raise HTTPException(
            status_code=404,
            detail=f"Station {station_id} not found"
        )
    
    try:
        forecast = await gfs_client.get_station_wind_forecast(station)
    except Exception as e:
        logger.error(f"Failed to fetch wind forecast for station {station_id}: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Wind forecast service temporarily unavailable"
        )
        
    if not forecast:
        raise HTTPException(
            status_code=503,
            detail="No forecast data available"
        )
            
    return forecast

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