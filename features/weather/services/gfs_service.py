import getgfs
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException
import numpy as np
import xarray as xr

from features.wind.models.wind_types import WindData, WindForecast
from features.common.models.station_types import StationInfo
from core.cache import cached

logger = logging.getLogger(__name__)

class GFSForecastManager:
    def __init__(self):
        self.forecast: Optional[getgfs.Forecast] = None
        self.last_update: Optional[datetime] = None
        self.update_interval = timedelta(hours=6)
        
    async def initialize(self) -> None:
        """Initialize GFS data on startup."""
        try:
            logger.info("Initializing GFS forecast data...")
            self.forecast = getgfs.Forecast("0p25")
            self.last_update = datetime.now(timezone.utc)
            logger.info(f"GFS forecast initialized at {self.last_update}")
        except Exception as e:
            logger.error(f"Failed to initialize GFS forecast: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="Unable to initialize GFS forecast data"
            )
    
    def should_update(self) -> bool:
        """Check if forecast needs updating based on model run schedule."""
        if not self.last_update:
            return True
            
        current_hour = datetime.now(timezone.utc).hour
        # GFS runs at 00, 06, 12, and 18 UTC
        # Add 1 hour buffer for data availability
        next_run = (current_hour // 6) * 6 + 6
        if current_hour >= 18:
            next_run = 0  # Next day 00z run
            
        return datetime.now(timezone.utc) - self.last_update >= timedelta(hours=6)
    
    async def update_forecast(self) -> None:
        """Update GFS forecast data."""
        try:
            if self.should_update():
                logger.info("Updating GFS forecast data...")
                self.forecast = getgfs.Forecast("0p25")
                self.last_update = datetime.now(timezone.utc)
                logger.info(f"GFS forecast updated at {self.last_update}")
        except Exception as e:
            logger.error(f"Failed to update GFS forecast: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="Unable to fetch latest GFS forecast data"
            )

    def _calculate_wind(self, u: float, v: float) -> tuple[float, float]:
        """Calculate wind speed and direction from U and V components."""
        try:
            speed = round(math.sqrt(u * u + v * v), 2)
            direction = round(math.degrees(math.atan2(-u, -v)) % 360, 2)
            return speed, direction
        except Exception as e:
            logger.error(f"Error calculating wind: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error calculating wind data: {str(e)}"
            )

    def get_station_wind_data(self, station_id: str, station_info: Dict) -> WindData:
        """Get current wind conditions for a station."""
        if not self.forecast:
            raise HTTPException(
                status_code=503,
                detail="Forecast data not available"
            )
            
        try:
            lat = station_info["location"]["coordinates"][1]
            lon = station_info["location"]["coordinates"][0]
            current_time = datetime.now(timezone.utc)
            
            # Get forecast date, time and query time
            forecast_date, forecast_time, query_time = self.forecast.datetime_to_forecast(
                current_time.strftime("%Y%m%d %H:%M")
            )
            
            # Get wind data from GFS
            result = self.forecast.get(
                ["ugrd10m", "vgrd10m", "gustsfc"],
                current_time.strftime("%Y%m%d %H:%M"),
                lat,
                lon
            )
            
            # Extract values from the response
            u = float(result.variables["ugrd10m"].data[0][0][0])
            v = float(result.variables["vgrd10m"].data[0][0][0])
            gust = round(float(result.variables["gustsfc"].data[0][0][0]), 2)
            
            # Calculate wind speed and direction
            speed, direction = self._calculate_wind(u, v)
            
            return WindData(
                station_id=station_id,
                station_name=station_info["name"],
                latitude=lat,
                longitude=lon,
                timestamp=current_time,
                wind_speed=speed,
                wind_gust=gust,
                wind_direction=direction
            )
            
        except Exception as e:
            logger.error(f"Error getting wind data for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind data: {str(e)}"
            )

    def get_station_wind_forecast(self, station_id: str, station_info: Dict) -> WindForecast:
        """Get 7-day wind forecast for a station."""
        if not self.forecast:
            raise HTTPException(
                status_code=503,
                detail="Forecast data not available"
            )
            
        try:
            lat = station_info["location"]["coordinates"][1]
            lon = station_info["location"]["coordinates"][0]
            forecasts = []
            
            # Get the latest forecast run time
            current_time = datetime.now(timezone.utc)
            
            # Get all forecast data at once with time range
            result = self.forecast.get(
                ["ugrd10m", "vgrd10m", "gustsfc"],
                current_time.strftime("%Y%m%d %H:%M"),
                str(lat),  # Convert to string as required by the API
                str(lon),  # Convert to string as required by the API
            )
            
            # Get the time dimension size from the data
            time_steps = len(result.variables["ugrd10m"].data)
            logger.info(f"Retrieved {time_steps} time steps from GFS")
            
            # Get forecast times for next 7 days at 3-hour intervals
            forecast_times = []
            for i in range(0, 169, 3):  # 0 to 168 hours (7 days) in 3-hour steps
                forecast_time = current_time + timedelta(hours=i)
                result = self.forecast.get(
                    ["ugrd10m", "vgrd10m", "gustsfc"],
                    forecast_time.strftime("%Y%m%d %H:%M"),
                    str(lat),
                    str(lon)
                )
                
                try:
                    # Extract values for this time step
                    u = float(result.variables["ugrd10m"].data[0][0][0])
                    v = float(result.variables["vgrd10m"].data[0][0][0])
                    gust = round(float(result.variables["gustsfc"].data[0][0][0]), 2)
                    
                    # Calculate wind speed and direction
                    speed, direction = self._calculate_wind(u, v)
                    
                    forecasts.append(WindData(
                        station_id=station_id,
                        station_name=station_info["name"],
                        latitude=lat,
                        longitude=lon,
                        timestamp=forecast_time,
                        wind_speed=speed,
                        wind_gust=gust,
                        wind_direction=direction
                    ))
                except Exception as e:
                    logger.warning(f"Error processing forecast at time {forecast_time}: {str(e)}")
                    continue
            
            if not forecasts:
                raise HTTPException(
                    status_code=503,
                    detail="No forecast data available"
                )
            
            logger.info(f"Processed {len(forecasts)} forecasts for station {station_id}")
            
            return WindForecast(
                station_id=station_id,
                station_name=station_info["name"],
                latitude=lat,
                longitude=lon,
                forecasts=forecasts
            )
            
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind forecast: {str(e)}"
            ) 