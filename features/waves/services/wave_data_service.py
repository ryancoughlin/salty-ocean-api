import logging
from typing import Dict, List
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone

from features.waves.models.wave_types import (
    WaveForecastPoint,
    WaveForecastResponse
)
from core.cache import cached
from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient
from features.stations.services.station_service import StationService

logger = logging.getLogger(__name__)

class WaveDataService:
    def __init__(
        self, 
        gfs_client: NOAAGFSClient,
        buoy_client: NDBCBuoyClient,
        station_service: StationService
    ):
        self.gfs_client = gfs_client
        self.buoy_client = buoy_client
        self.station_service = station_service

    @cached(
        namespace="wave_forecast",
        expire=14400  # 4 hours (max time between model runs)
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
                
            # Get forecast directly from GFS wave service
            gfs_forecast = await self.gfs_client.get_station_forecast(station_id, station)
            
            if not gfs_forecast:
                logger.error(f"No forecast data available for station {station_id}")
                raise HTTPException(
                    status_code=503,
                    detail="Forecast data not available. Please try again later."
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
                point_hour = point.timestamp.replace(minute=0, second=0, microsecond=0)
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
            
            return WaveForecastResponse(
                station=station,
                forecasts=forecast_points,
                model_run=f"{gfs_forecast.cycle.date} {gfs_forecast.cycle.hour}z"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


    @cached(namespace="wave_stations_geojson")
    async def get_stations_geojson(self) -> Dict:
        """Get all wave monitoring stations in GeoJSON format."""
        try:
            stations = self.station_service.get_stations()
            
            features = []
            for station in stations:
                feature = {
                    "type": "Feature",
                    "geometry": station.location.dict(),
                    "properties": {
                        "id": station.station_id,
                        "name": station.name,
                    }
                }
                features.append(feature)
            
            return {
                "type": "FeatureCollection",
                "features": features
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error converting stations to GeoJSON: {str(e)}"
            ) 