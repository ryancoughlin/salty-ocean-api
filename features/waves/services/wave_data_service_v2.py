import logging
from typing import Dict, List, Optional
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from aiocache import cached, SimpleMemoryCache

from features.waves.models.wave_types import (
    WaveForecastPoint,
    WaveForecastResponse
)
from features.waves.services.gfs_wave_client import GFSWaveClient
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient
from features.stations.services.station_service import StationService
from features.common.services.model_run_service import ModelRun
from features.common.services.cache_config import (
    MODEL_FORECAST_EXPIRE,
    feature_cache_key_builder,
    get_cache
)
from core.config import settings

logger = logging.getLogger(__name__)

class WaveDataServiceV2:
    # Default forecast range in days if not specified in settings
    DEFAULT_FORECAST_DAYS = 7
    
    def __init__(
        self, 
        gfs_client: GFSWaveClient,
        buoy_client: NDBCBuoyClient,
        station_service: StationService
    ):
        self.gfs_client = gfs_client
        self.buoy_client = buoy_client
        self.station_service = station_service
        self._cache = get_cache()
        # Get forecast days from settings or use default
        self.forecast_days = getattr(settings, 'wave_forecast_days', self.DEFAULT_FORECAST_DAYS)
        logger.info(f"Wave forecast range set to {self.forecast_days} days")

    async def handle_model_run_update(self, model_run: ModelRun):
        """Handle model run update by clearing affected cache entries."""
        logger.info(f"🔄 Updating wave data service to model run: {model_run}")
        
        try:
            # Get all cache keys matching the pattern
            keys = await self._cache.raw("keys", "wave_forecast:*")
            if keys:
                logger.info(f"Found {len(keys)} wave forecast cache entries to invalidate")
                for key in keys:
                    await self._cache.delete(key)
                logger.info(f"🗑️ Cleared {len(keys)} wave forecast cache entries for new model run")
            else:
                logger.info("No wave forecast cache entries to clear")
        except Exception as e:
            logger.error(f"Error clearing wave forecast cache: {str(e)}")
            # Continue even if cache clearing fails - better to serve stale data than no data

    @cached(
        ttl=MODEL_FORECAST_EXPIRE,
        key_builder=feature_cache_key_builder,
        namespace="wave_forecast",
        cache=SimpleMemoryCache,
        noself=True
    )
    async def get_station_forecast(self, station_id: str) -> WaveForecastResponse:
        """Get wave model forecast for a specific station."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
                
            try:
                # Get forecast from GFS wave service
                gfs_forecast = await self.gfs_client.get_station_forecast(station_id, station)
                
                if not gfs_forecast.forecasts:
                    logger.warning(f"No forecast data available for station {station_id}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"No forecast data available for station {station_id}"
                    )
                
                # Set time range based on configuration
                now = datetime.now(timezone.utc)
                end_time = now + timedelta(days=self.forecast_days)
                
                # Round current time down to nearest 3-hour interval
                now = now.replace(minute=0, second=0, microsecond=0)
                now = now.replace(hour=(now.hour // 3) * 3)
                
                # Convert to API response format with proper null handling
                forecast_points = []
                for point in gfs_forecast.forecasts:
                    # Only include points within configured day range and at 3-hour intervals
                    point_hour = point.time.replace(minute=0, second=0, microsecond=0)
                    if (point_hour >= now and 
                        point_hour <= end_time and 
                        point_hour.hour % 3 == 0):
                        # Get primary wave component (highest) with null safety
                        primary_wave = point.waves[0] if point.waves else None
                        
                        # Create forecast point with safe null handling
                        forecast_points.append(WaveForecastPoint(
                            time=point_hour,
                            height=primary_wave.height_ft if primary_wave else 0.0,
                            period=primary_wave.period if primary_wave else 0.0,
                            direction=primary_wave.direction if primary_wave else 0.0
                        ))
                
                # Sort forecasts by time to ensure order
                forecast_points.sort(key=lambda x: x.time)
                
                # Get model run info from the forecast
                model_run = f"{gfs_forecast.cycle.date} {gfs_forecast.cycle.hour}z"
                
                response = WaveForecastResponse(
                    station=station,
                    forecasts=forecast_points,
                    model_run=model_run
                )
                
                # Log cache key for debugging
                cache_key = feature_cache_key_builder(
                    self.get_station_forecast,
                    namespace="wave_forecast",
                    station_id=station_id
                )
                logger.info(f"Caching forecast for station {station_id} with key {cache_key}")
                
                return response
                
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