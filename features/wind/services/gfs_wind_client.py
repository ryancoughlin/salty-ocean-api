import aiohttp
import logging
import numpy as np
import xarray as xr
import cfgrib
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
import asyncio
from fastapi import HTTPException

from features.wind.models.wind_types import WindForecastResponse, WindForecastPoint
from features.common.models.station_types import Station
from features.common.utils.conversions import UnitConversions
from features.wind.utils.file_storage import GFSFileStorage
from features.common.services.model_run_service import ModelRun

logger = logging.getLogger(__name__)

class GFSWindClient:
    """Client for fetching wind data from NOAA's GFS using NOMADS GRIB Filter."""
    
    BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    
    REGIONS = {
        "atlantic": {
            "lat": {"start": 0, "end": 55, "resolution": 0.25},
            "lon": {"start": 260, "end": 310, "resolution": 0.25}  # -100 to -50 in 360-notation
        },
        "pacific": {
            "lat": {"start": 0, "end": 60, "resolution": 0.25},
            "lon": {"start": 180, "end": 245, "resolution": 0.25}
        }
    }
    
    # Rate limiting constants
    REQUESTS_PER_MINUTE = 120
    REQUEST_INTERVAL = 60 / REQUESTS_PER_MINUTE  # Time between requests in seconds
    BATCH_SIZE = 30  # Number of requests to make before pausing
    BATCH_PAUSE = 15  # Seconds to pause after each batch
    
    def __init__(self, model_run: Optional[ModelRun] = None):
        self.model_run = model_run
        self.file_storage = GFSFileStorage()
        self._regional_datasets = {}
        self._is_initialized = False
        self._initialization_lock = asyncio.Lock()
        self._initialization_error: Optional[str] = None
        self.forecast_hours = list(range(0, 385, 3))  # 0 to 384 by 3-hour steps
        self._request_count = 0
        self._last_request_time = datetime.now()
        
    def update_model_run(self, model_run: ModelRun):
        """Update the current model run and clean up old files."""
        logger.info(f"🔄 Updating wind client model run to: {model_run}")
        self.model_run = model_run
        self.file_storage.cleanup_old_files(model_run)
        self._regional_datasets = {}
        self._is_initialized = False
        self._initialization_error = None
        
    async def initialize(self):
        """Initialize the wind client by loading the latest model run data."""
        async with self._initialization_lock:
            if self._is_initialized:
                return
                
            if not self.model_run:
                self._initialization_error = "No model cycle currently available"
                raise HTTPException(
                    status_code=503,
                    detail=self._initialization_error
                )
            
            initialization_errors = []
            
            # Initialize each region
            for region in self.REGIONS.keys():
                try:
                    logger.info(f"🌎 Initializing {region} region wind data...")
                    missing_files = self.file_storage.get_missing_files(
                        region,
                        self.model_run,
                        self.forecast_hours
                    )
                    
                    if missing_files:
                        logger.info(f"📥 Downloading {len(missing_files)} wind files for {region}...")
                        downloaded, failed = await self._download_regional_files(region, missing_files)
                        logger.info(f"📊 {region} wind download summary: {downloaded} succeeded, {failed} failed")

                    else:
                        logger.info(f"✨ All wind files already available for {region}")
                    
                    # Load the dataset
                    valid_files = self.file_storage.get_valid_files(
                        region,
                        self.model_run,
                        self.forecast_hours
                    )
                    
                    if not valid_files:
                        error_msg = f"No valid wind files available for {region}"
                        initialization_errors.append(error_msg)
                        logger.error(f"❌ {error_msg}")
                        continue
                        
                    logger.info(f"🔄 Loading {len(valid_files)} wind files for {region}...")
                    
                    # Load each file into a dataset
                    for file_path in valid_files:
                        try:
                            forecast_hour = int(str(file_path).split('_f')[-1].split('.')[0])
                            ds = xr.open_dataset(
                                file_path,
                                engine='cfgrib',
                                decode_timedelta=False,
                                backend_kwargs={'indexpath': ''}
                            )
                            cache_key = f"{region}_{self.model_run.date_str}_{self.model_run.cycle_hour:02d}_{forecast_hour:03d}"
                            self._regional_datasets[cache_key] = ds
                        except Exception as e:
                            logger.error(f"❌ Error loading wind file {file_path}: {str(e)}")
                            continue
                            
                    logger.info(f"✅ Successfully loaded wind data for {region}")
                        
                except Exception as e:
                    error_msg = f"Error initializing {region} wind data: {str(e)}"
                    initialization_errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    continue
            
            if initialization_errors:
                self._initialization_error = "; ".join(initialization_errors)
                logger.error(f"❌ Wind initialization errors: {self._initialization_error}")
            else:
                self._is_initialized = True
                logger.info("✅ Wind client initialization complete!")

    async def _ensure_initialized(self):
        """Ensure the client is initialized before processing requests."""
        if not self._is_initialized:
            try:
                await self.initialize()
            except Exception as e:
                logger.error(f"❌ Wind initialization failed: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail=self._initialization_error or "Wind service initialization failed"
                )

    def _get_region_for_station(self, lat: float, lon: float) -> str:
        """Determine which region a station belongs to."""
        if lon < 0:
            lon = 360 + lon
            
        for region, bounds in self.REGIONS.items():
            if (bounds["lat"]["start"] <= lat <= bounds["lat"]["end"] and
                bounds["lon"]["start"] <= lon <= bounds["lon"]["end"]):
                return region
                
        raise HTTPException(
            status_code=400,
            detail=f"Station coordinates ({lat}, {lon}) not within supported regions"
        )
    
    def _build_grib_filter_url(
        self,
        forecast_hour: int,
        region: str
    ) -> str:
        """Build URL for NOMADS GRIB filter service for a region."""
        bounds = self.REGIONS[region]
        
        params = {
            "dir": f"/gfs.{self.model_run.date_str}/{self.model_run.cycle_hour:02d}/atmos",
            "file": f"gfs.t{self.model_run.cycle_hour:02d}z.pgrb2.0p25.f{forecast_hour:03d}",
            "var_UGRD": "on",
            "var_VGRD": "on",
            "var_GUST": "on",
            "lev_10_m_above_ground": "on",
            "lev_surface": "on",
            "subregion": "",
            "toplat": f"{bounds['lat']['end']}",
            "bottomlat": f"{bounds['lat']['start']}",
            "leftlon": f"{bounds['lon']['start']}",
            "rightlon": f"{bounds['lon']['end']}"
        }
        
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))  # Sort params for consistent order
        url = f"https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?{query}"
        logger.info(f"Building URL for {url}")
        return url
            
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
            
    def _process_grib_data(
        self,
        ds: xr.Dataset,
        lat: float,
        lon: float
    ) -> Optional[Tuple[datetime, float, float, float]]:
        """Process GRIB2 dataset and extract wind data for location."""
        try:
            valid_time = pd.to_datetime(ds.valid_time.item()).to_pydatetime()
            if not isinstance(valid_time, datetime):
                logger.error(f"Invalid time format from GRIB: {valid_time}")
                return None
            
            if valid_time.tzinfo is None:
                valid_time = valid_time.replace(tzinfo=timezone.utc)
            
            lat_idx = abs(ds.latitude - lat).argmin().item()
            lon_idx = abs(ds.longitude - lon).argmin().item()
            
            u = float(ds['u10'].values[lat_idx, lon_idx])
            v = float(ds['v10'].values[lat_idx, lon_idx])
            gust = float(ds['gust'].values[lat_idx, lon_idx])
            
            return valid_time, u, v, gust
            
        except Exception as e:
            logger.error(f"Error processing GRIB data: {str(e)}")
            return None
    
    async def _prepare_regional_dataset(
        self,
        region: str,
        forecast_hour: int
    ) -> xr.Dataset:
        """Prepare regional dataset for processing."""
        try:
            cache_key = f"{region}_{self.model_run.date_str}_{self.model_run.cycle_hour:02d}_{forecast_hour:03d}"
            if cache_key in self._regional_datasets:
                return self._regional_datasets[cache_key]
            
            url = self._build_grib_filter_url(forecast_hour, region)
            file_path = self.file_storage.get_regional_file_path(region, self.model_run, forecast_hour)
            
            if not self.file_storage.is_file_valid(file_path):
                async with aiohttp.ClientSession(
                    cookies={'osCsid': 'dummy'},  # Required for NOAA's filter service
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                        'Accept': '*/*'
                    }
                ) as session:
                    async with session.get(url, allow_redirects=False, timeout=300) as response:
                        print("Downloading new data")
                        if response.status == 200:
                            content = await response.read()
                            await self.file_storage.save_file(file_path, content)
                        else:
                            logger.error(f"Initial request failed with status {response.status}")
                            raise HTTPException(
                                status_code=503,
                                detail=f"Failed to download regional GRIB file: {response.status}"
                            )
            
            ds = xr.open_dataset(
                file_path,
                engine='cfgrib',
                decode_timedelta=False,
                backend_kwargs={'indexpath': ''}
            )
            
            self._regional_datasets[cache_key] = ds
            return ds
            
        except Exception as e:
            logger.error(f"Error preparing regional dataset for {region}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error preparing regional dataset: {str(e)}"
            )

    async def get_station_wind_forecast(self, station_id: str, station: Station) -> WindForecastResponse:
        """Get wind forecast for a station using regional data."""
        try:
            await self._ensure_initialized()
            
            if not self.model_run:
                raise HTTPException(
                    status_code=503,
                    detail="No model cycle currently available"
                )
            
            lat = station.location.coordinates[1]
            lon = station.location.coordinates[0]
            region = self._get_region_for_station(lat, lon)
            
            forecasts: List[WindForecastPoint] = []
            total_hours = 0
            failed_hours = 0
            
            for hour in range(0, 385, 3):
                try:
                    ds = await self._prepare_regional_dataset(region, hour)
                    wind_data = self._process_grib_data(ds, lat, lon)
                    
                    if wind_data:
                        valid_time, u, v, gust = wind_data
                        speed, direction = self._calculate_wind(u, v)
                        
                        forecasts.append(WindForecastPoint(
                            time=valid_time,
                            speed=UnitConversions.ms_to_mph(speed),
                            direction=direction,
                            gust=UnitConversions.ms_to_mph(gust)
                        ))
                        total_hours += 1
                        
                except Exception as e:
                    logger.error(f"Error processing hour {hour}: {str(e)}")
                    failed_hours += 1
                    continue
            
            if not forecasts:
                raise HTTPException(
                    status_code=503,
                    detail=f"No forecast data available. Failed to process {failed_hours} forecast hours."
                )
            
            return WindForecastResponse(
                station=station,
                model_run=f"{self.model_run.date_str}_{self.model_run.cycle_hour:02d}Z",
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

    async def _fetch_content(self, url: str, timeout: int = 300) -> Optional[bytes]:
        """Simple helper to fetch content from URL, handling redirects."""
        try:
            async with aiohttp.ClientSession(
                cookies={'osCsid': 'dummy'},
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            ) as session:
                async with session.get(url, allow_redirects=True, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.error(f"Failed to fetch {url}: status {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def _rate_limit(self):
        """Implement rate limiting logic."""
        now = datetime.now()
        
        # Reset counter if a minute has passed
        if (now - self._last_request_time).total_seconds() >= 60:
            self._request_count = 0
            self._last_request_time = now
            
        # If we've hit our batch size, pause
        if self._request_count > 0 and self._request_count % self.BATCH_SIZE == 0:
            logger.info(f"⏸️ Pausing for {self.BATCH_PAUSE}s after batch of {self.BATCH_SIZE} requests...")
            await asyncio.sleep(self.BATCH_PAUSE)
            self._request_count = 0
            self._last_request_time = datetime.now()
            return
            
        # Otherwise, small delay between requests
        if self._request_count > 0:
            await asyncio.sleep(self.REQUEST_INTERVAL)
            
        self._request_count += 1

    async def _download_grib_file(
        self,
        url: str,
        file_path: Path,
    ) -> bool:
        """Download a single GRIB file and save it."""
        if self.file_storage.is_file_valid(file_path):
            return True

        try:
            # Apply rate limiting before request
            await self._rate_limit()
            
            async with aiohttp.ClientSession(
                cookies={'osCsid': 'dummy'},
                headers={
                    'User-Agent': 'curl/7.81.0',
                    'Accept': '*/*'
                }
            ) as session:
                async with session.get(url, timeout=300) as response:
                   
                    if response.status == 200:
                        content = await response.read()

                        if await self.file_storage.save_file(file_path, content):
                            return True
                    else:
                        logger.error(f"Download failed with status {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return False

    async def _download_regional_files(
        self,
        region: str,
        missing_files: List[Tuple[int, Path]]
    ) -> Tuple[int, int]:
        """Download missing files for a region."""
        downloaded = failed = 0
        
        for forecast_hour, file_path in missing_files:
            url = self._build_grib_filter_url(forecast_hour, region)
            if await self._download_grib_file(url, file_path):
                downloaded += 1
            else:
                failed += 1
                
        return downloaded, failed 