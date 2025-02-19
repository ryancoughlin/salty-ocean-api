import aiohttp
import logging
import numpy as np
import xarray as xr
import cfgrib
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
import asyncio
from fastapi import HTTPException

from features.wind.models.wind_types import WindForecastResponse, WindForecastPoint
from features.common.models.station_types import Station
from features.common.utils.conversions import UnitConversions
from features.wind.utils.file_storage import GFSFileStorage
from features.common.services.model_run_service import ModelRunService
from features.common.exceptions.model_run_exceptions import (
    CycleDownloadError,
    CycleValidationError
)

logger = logging.getLogger(__name__)

class GFSWindClient:
    """Client for fetching wind data from NOAA's GFS using NOMADS GRIB Filter."""
    
    BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    
    def __init__(self, model_run_service: Optional[ModelRunService] = None):
        self.file_storage = GFSFileStorage()
        self.model_run_service = model_run_service or ModelRunService()
        
    def _build_grib_filter_url(self, date: datetime, cycle: str, forecast_hour: int,
                              lat: float, lon: float) -> str:
        """Build URL for NOMADS GRIB filter service."""
        # Convert longitude to 0-360 range if needed
        if lon < 0:
            lon = 360 + lon
            
        # Create 1-degree bounding box
        lat_buffer = 0.15
        lon_buffer = 0.15
        
        params = {
            "dir": f"/gfs.{date.strftime('%Y%m%d')}/{cycle}/atmos",
            "file": f"gfs.t{cycle}z.pgrb2.0p25.f{forecast_hour:03d}",
            "var_UGRD": "on",
            "var_VGRD": "on",
            "var_GUST": "on",
            "lev_10_m_above_ground": "on",
            "lev_surface": "on",
            "subregion": "",
            "toplat": f"{lat + lat_buffer}",
            "bottomlat": f"{lat - lat_buffer}",
            "leftlon": f"{lon - lon_buffer}",
            "rightlon": f"{lon + lon_buffer}"
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE_URL}?{query}"
    
    async def _get_grib_file(self, url: str, station_id: str, date: datetime, 
                            cycle: str, forecast_hour: int) -> Optional[Path]:
        """Get GRIB file from storage or download if needed."""
        file_path = self.file_storage.get_file_path(station_id, date, cycle, forecast_hour)
        
        # Check if we have a valid cached file
        if self.file_storage.is_file_valid(file_path):
            logger.debug(f"Using cached GRIB file for station {station_id}")
            return file_path
            
        # Download if no valid file exists
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True, timeout=300) as response:
                    if response.status == 404:
                        logger.error("GRIB2 file not found")
                        raise CycleDownloadError("GRIB2 file not found")
                    elif response.status != 200:
                        logger.error(f"Failed to download GRIB2 file: {response.status}")
                        raise CycleDownloadError(f"Failed to download GRIB2 file: {response.status}")
                        
                    content = await response.read()
                    if len(content) < 100:
                        logger.error("Downloaded file too small to be valid GRIB2")
                        raise CycleValidationError("Downloaded file too small to be valid GRIB2")
                        
                    if await self.file_storage.save_file(file_path, content):
                        return file_path
                    return None
            
        except asyncio.TimeoutError:
            logger.error("Timeout while downloading GRIB2 file")
            raise CycleDownloadError("Timeout while downloading GRIB2 file")
        except Exception as e:
            logger.error(f"Error downloading GRIB2 file: {str(e)}")
            raise CycleDownloadError(f"Error downloading GRIB2 file: {str(e)}")
    
    def _calculate_wind(self, u: float, v: float) -> tuple[float, float]:
        """Calculate wind speed and direction from U and V components."""
        try:
            speed = round((u * u + v * v) ** 0.5, 2)
            direction = round((270 - (180 / 3.14159) * (v > 0) * 3.14159 + (180 / 3.14159) * (v < 0) * 3.14159) % 360, 2)
            return speed, direction
        except Exception as e:
            logger.error(f"Error calculating wind: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error calculating wind data: {str(e)}"
            )
            
    def _process_grib_data(self, grib_path: Path, lat: float, lon: float) -> Optional[Tuple[datetime, float, float, float]]:
        """Process GRIB2 file and extract wind data for location."""
        try:
            ds = xr.open_dataset(
                grib_path,
                engine='cfgrib',
                backend_kwargs={'indexpath': ''}
            )
            
            try:
                # Get valid time from the dataset and ensure it's a datetime
                valid_time = pd.to_datetime(ds.valid_time.item()).to_pydatetime()
                if not isinstance(valid_time, datetime):
                    logger.error(f"Invalid time format from GRIB: {valid_time}")
                    return None
                
                # Ensure timezone is UTC
                if valid_time.tzinfo is None:
                    valid_time = valid_time.replace(tzinfo=timezone.utc)
                
                # Find nearest grid point
                lat_idx = abs(ds.latitude - lat).argmin().item()
                lon_idx = abs(ds.longitude - lon).argmin().item()
                
                # Extract values using known variable names - data is 2D (lat, lon)
                u = float(ds['u10'].values[lat_idx, lon_idx])
                v = float(ds['v10'].values[lat_idx, lon_idx])
                gust = float(ds['gust'].values[lat_idx, lon_idx])
                
                return valid_time, u, v, gust
            finally:
                ds.close()
                
        except Exception as e:
            logger.error(f"Error processing GRIB2 file: {str(e)}")
            return None
    
    async def get_station_wind_forecast(self, station: Station) -> WindForecastResponse:
        """Get 7-day wind forecast for a station."""
        try:
            cycle_date, cycle_hour = await self.model_run_service.get_latest_available_cycle()
            forecasts: List[WindForecastPoint] = []
            
            # Get lat/lon from GeoJSON coordinates [lon, lat]
            lat = station.location.coordinates[1]
            lon = station.location.coordinates[0]
            
            # Get forecasts at 3-hour intervals up to 168 hours (7 days)
            for hour in range(0, 169, 3):  # 0 to 168 inclusive
                url = self._build_grib_filter_url(
                    cycle_date, cycle_hour, hour,
                    lat, lon
                )
                
                grib_path = await self._get_grib_file(url, station.station_id, cycle_date, cycle_hour, hour)
                if not grib_path:
                    logger.debug(f"Missing forecast for hour {hour}")
                    continue
                    
                wind_data = self._process_grib_data(grib_path, lat, lon)
                if wind_data:
                    valid_time, u, v, gust = wind_data
                    speed, direction = self._calculate_wind(u, v)
                    
                    forecasts.append(WindForecastPoint(
                        time=valid_time,
                        speed=UnitConversions.ms_to_mph(speed),
                        direction=direction,
                        gust=UnitConversions.ms_to_mph(gust)
                    ))
            
            if not forecasts:
                raise HTTPException(
                    status_code=503,
                    detail="No forecast data available"
                )
                
            # Sort forecasts by time
            forecasts.sort(key=lambda x: x.time)
            
            return WindForecastResponse(
                station_id=station.station_id,
                name=station.name,
                location=station.location,
                model_run=f"{cycle_date.strftime('%Y%m%d')}_{cycle_hour}Z",
                forecasts=forecasts
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station.station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind forecast: {str(e)}"
            ) 