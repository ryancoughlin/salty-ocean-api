import logging
from typing import Dict, List
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import asyncio

from features.wind.models.wind_types import (
    WindForecastPoint,
    WindForecastResponse
)
from core.cache import cached
from features.wind.services.gfs_wind_client import GFSWindClient
from features.stations.services.station_service import StationService
from features.common.services.model_run_service import ModelRun

logger = logging.getLogger(__name__)

def wind_forecast_key_builder(
    func,
    namespace: str = "",
    *args,
    **kwargs
) -> str:
    """Build cache key for wind forecast endpoint."""
    station_id = kwargs.get("station_id", "")
    return f"{namespace}:{station_id}"

class WindDataService:
    def __init__(
        self, 
        gfs_client: GFSWindClient,
        station_service: StationService
    ):
        self.gfs_client = gfs_client
        self.station_service = station_service
        self._initialization_lock = asyncio.Lock()
        self._is_initialized = False
        
    async def initialize(self):
        """Initialize the wind data service."""
        async with self._initialization_lock:
            if self._is_initialized:
                return
                
            try:
                logger.info("🌬️ Initializing wind data service...")
                await self.gfs_client.initialize()
                self._is_initialized = True
                logger.info("✅ Wind data service initialization complete!")
            except Exception as e:
                logger.error(f"❌ Wind data service initialization failed: {str(e)}")
                raise
                
    async def handle_model_run_update(self, model_run: ModelRun):
        """Handle model run update by reinitializing the service."""
        logger.info(f"🔄 Updating wind data service to model run: {model_run}")
        self.gfs_client.update_model_run(model_run)
        self._is_initialized = False
        await self.initialize()

    @cached(
        namespace="wind_forecast",
        expire=14400,  # 4 hours (max time between model runs)
        key_builder=wind_forecast_key_builder
    )
    async def get_station_forecast(self, station_id: str) -> WindForecastResponse:
        """Get wind model forecast for a specific station."""
        try:
            if not self._is_initialized:
                await self.initialize()
                
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
                
            try:
                # Get forecast from GFS wind service
                forecast = await self.gfs_client.get_station_wind_forecast(station)
                
                if not forecast.forecasts:
                    logger.warning(f"No forecast data available for station {station_id}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"No forecast data available for station {station_id}"
                    )
                
                # Set time range for exactly 7 days
                now = datetime.now(timezone.utc)
                end_time = now + timedelta(days=7)
                
                # Round current time down to nearest 3-hour interval
                now = now.replace(minute=0, second=0, microsecond=0)
                now = now.replace(hour=(now.hour // 3) * 3)
                
                # Filter forecasts to 7-day range and 3-hour intervals
                filtered_forecasts = []
                for point in forecast.forecasts:
                    point_hour = point.time.replace(minute=0, second=0, microsecond=0)
                    if (point_hour >= now and 
                        point_hour <= end_time and 
                        point_hour.hour % 3 == 0):
                        filtered_forecasts.append(point)
                
                # Sort forecasts by time to ensure order
                filtered_forecasts.sort(key=lambda x: x.time)
                
                return WindForecastResponse(
                    station=station,
                    forecasts=filtered_forecasts,
                    model_run=forecast.model_run
                )
                
            except Exception as e:
                logger.error(f"Error getting GFS forecast for station {station_id}: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="Error getting forecast data. Please try again later."
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get_station_forecast for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e)) 