import logging
from typing import Dict, List
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import asyncio

from features.waves.models.wave_types import (
    WaveForecastPoint,
    WaveForecastResponse
)
from core.cache import cached
from features.waves.services.gfs_wave_client import GFSWaveClient
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient
from features.stations.services.station_service import StationService

logger = logging.getLogger(__name__)

def wave_forecast_key_builder(
    func,
    namespace: str = "",
    station_id: str = "",
    *args,
    **kwargs
) -> str:
    """Build cache key for wave forecast endpoint."""
    return f"{namespace}:{station_id}"

class WaveDataServiceV2:
    def __init__(
        self, 
        gfs_client: GFSWaveClient,
        buoy_client: NDBCBuoyClient,
        station_service: StationService
    ):
        self.gfs_client = gfs_client
        self.buoy_client = buoy_client
        self.station_service = station_service

    @cached(
        namespace="wave_forecast",
        expire=14400,  # 4 hours (max time between model runs)
        key_builder=wave_forecast_key_builder
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
                
                # Set time range for exactly 7 days
                now = datetime.now(timezone.utc)
                end_time = now + timedelta(days=7)
                
                # Round current time down to nearest 3-hour interval
                now = now.replace(minute=0, second=0, microsecond=0)
                now = now.replace(hour=(now.hour // 3) * 3)
                
                # Convert to API response format
                forecast_points = []
                for point in gfs_forecast.forecasts:
                    # Only include points within 7 day range and at 3-hour intervals
                    point_hour = point.time.replace(minute=0, second=0, microsecond=0)
                    if (point_hour >= now and 
                        point_hour <= end_time and 
                        point_hour.hour % 3 == 0):
                        # Get primary wave component (highest)
                        primary_wave = point.waves[0] if point.waves else None
                        forecast_points.append(WaveForecastPoint(
                            time=point_hour,
                            height=primary_wave.height_ft if primary_wave else None,
                            period=primary_wave.period if primary_wave else None,
                            direction=primary_wave.direction if primary_wave else None
                        ))
                
                # Sort forecasts by time to ensure order
                forecast_points.sort(key=lambda x: x.time)
                
                # Get model run info from the forecast
                model_run = f"{gfs_forecast.cycle.date} {gfs_forecast.cycle.hour}z"
                
                return WaveForecastResponse(
                    station=station,
                    forecasts=forecast_points,
                    model_run=model_run
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