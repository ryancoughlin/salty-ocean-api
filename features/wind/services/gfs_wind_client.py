import aiohttp
import logging
import numpy as np
import xarray as xr
import cfgrib
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
import tempfile
import os

from features.wind.models.wind_types import WindData, WindForecastResponse
from features.common.models.station_types import StationInfo

logger = logging.getLogger(__name__)

class GFSWindClient:
    """Client for fetching wind data from NOAA's GFS using NOMADS GRIB Filter."""
    
    BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    
    def __init__(self):
        self.tmp_dir = Path(tempfile.gettempdir()) / "gfs_wind"
        self.tmp_dir.mkdir(exist_ok=True)
        
    async def _get_latest_cycle(self) -> Tuple[datetime, str]:
        """Get the latest available GFS cycle."""
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour
        
        # Find latest cycle (00, 06, 12, 18)
        cycles = [0, 6, 12, 18]
        current_cycle = max(cycle for cycle in cycles if cycle <= current_hour)
        
        # Check if current cycle is available (needs ~6 hours to process)
        if current_hour < current_cycle + 6:
            # Fall back to previous cycle
            idx = cycles.index(current_cycle)
            current_cycle = cycles[idx - 1] if idx > 0 else cycles[-1]
            if current_cycle > current_hour:
                current_time = current_time - timedelta(days=1)
                
        cycle_str = f"{current_cycle:02d}"
        return current_time, cycle_str
    
    def _build_grib_filter_url(self, date: datetime, cycle: str, forecast_hour: int,
                              lat: float, lon: float) -> str:
        """Build URL for NOMADS GRIB filter service."""
        # Convert longitude to 0-360 range if needed
        if lon < 0:
            lon = 360 + lon
            
        # Create 1-degree bounding box
        lat_buffer = 0.5
        lon_buffer = 0.5
        
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
    
    async def _download_grib(self, url: str, output_path: Path) -> Optional[Path]:
        """Download GRIB2 file from NOMADS."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download GRIB2 file: {response.status}")
                        return None
                        
                    content = await response.read()
                    if len(content) < 100:  # Basic size check for valid GRIB2 file
                        logger.error(f"Downloaded file too small to be valid GRIB2")
                        return None
                        
                    with open(output_path, 'wb') as f:
                        f.write(content)
                            
            return output_path
        except Exception as e:
            logger.error(f"Error downloading GRIB2 file: {str(e)}")
            return None
    
    def _calculate_wind(self, u: float, v: float) -> Tuple[float, float]:
        """Calculate wind speed and direction from U and V components."""
        speed = np.sqrt(u * u + v * v)
        direction = (270 - np.degrees(np.arctan2(v, u))) % 360
        return round(float(speed), 2), round(float(direction), 2)
    
    def _process_grib_data(self, grib_path: Path, lat: float, lon: float) -> Optional[Tuple[datetime, float, float, float]]:
        """Process GRIB2 file and extract wind data for location.
        
        Returns:
            Tuple of (valid_time, u_wind, v_wind, gust) if successful, None otherwise
        """
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
    
    async def get_station_wind_data(self, station: StationInfo) -> Optional[WindData]:
        """Get current wind conditions for a station."""
        try:
            current_time, cycle = await self._get_latest_cycle()
            
            # Get lat/lon from GeoJSON coordinates [lon, lat]
            lon, lat = station.location.coordinates
            
            # Download current analysis file
            url = self._build_grib_filter_url(
                current_time, cycle, 0,
                lat, lon
            )
            
            grib_path = self.tmp_dir / f"gfs_wind_{station.id}_current.grib2"
            if not await self._download_grib(url, grib_path):
                return None
                
            # Process GRIB data
            wind_data = self._process_grib_data(grib_path, lat, lon)
            if not wind_data:
                return None
                
            valid_time, u, v, gust = wind_data
            speed, direction = self._calculate_wind(u, v)
            
            # Clean up temporary file
            os.unlink(grib_path)
            
            return WindData(
                timestamp=valid_time,
                wind_speed=speed,
                wind_gust=round(float(gust), 2),
                wind_direction=direction
            )
            
        except Exception as e:
            logger.error(f"Error getting wind data for station {station.id}: {str(e)}")
            return None
    
    async def get_station_wind_forecast(self, station: StationInfo) -> Optional[WindForecastResponse]:
        """Get wind forecast for a station.
        
        Returns 7 days of forecast data at 3-hour intervals.
        Total of 56 time points (168 hours / 3 hour interval).
        Forecast times are taken directly from the GRIB files.
        """
        try:
            current_time, cycle = await self._get_latest_cycle()
            forecasts: List[WindData] = []
            
            # Get lat/lon from GeoJSON coordinates [lon, lat]
            lon, lat = station.location.coordinates
            
            # Get forecasts at 3-hour intervals up to 165 hours (56 time points)
            for hour in range(0, 168, 3):  # 0 to 165 inclusive, giving 56 points
                url = self._build_grib_filter_url(
                    current_time, cycle, hour,
                    lat, lon
                )
                
                grib_path = self.tmp_dir / f"gfs_wind_{station.id}_f{hour:03d}.grib2"
                if not await self._download_grib(url, grib_path):
                    logger.warning(f"Failed to download forecast for hour {hour}")
                    continue
                    
                wind_data = self._process_grib_data(grib_path, lat, lon)
                if wind_data:
                    valid_time, u, v, gust = wind_data
                    speed, direction = self._calculate_wind(u, v)
                    
                    forecasts.append(WindData(
                        timestamp=valid_time,
                        wind_speed=speed,
                        wind_gust=round(float(gust), 2),
                        wind_direction=direction
                    ))
                    
                # Clean up temporary file
                os.unlink(grib_path)
            
            if not forecasts:
                logger.error("No forecast data could be processed")
                return None
                
            # Sort forecasts by timestamp to ensure proper ordering
            forecasts.sort(key=lambda x: x.timestamp)
            
            return WindForecastResponse(
                station=station,
                forecasts=forecasts
            )
            
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station.id}: {str(e)}")
            return None 