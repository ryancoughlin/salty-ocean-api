import aiohttp
import logging
import numpy as np
import xarray as xr
import cfgrib
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import asyncio
from fastapi import HTTPException

from features.wind.models.wind_types import WindForecastResponse, WindForecastPoint
from features.common.models.station_types import Station
from features.common.utils.conversions import UnitConversions
from features.wind.utils.file_storage import GFSFileStorage
from features.common.services.model_run_service import ModelRun
from features.common.services.rate_limiter import RateLimiter
from core.config import settings

logger = logging.getLogger(__name__)

class GFSWindClient:
    """Client for fetching wind data from NOAA's GFS using NOMADS GRIB Filter."""
    
    def __init__(self, model_run: Optional[ModelRun] = None):
        self.model_run = model_run
        self.file_storage = GFSFileStorage()
        self._is_initialized = False
        self._initialization_lock = asyncio.Lock()
        self._initialization_error: Optional[str] = None
        self.forecast_hours = settings.wind.forecast_hours
        self._datasets: Dict[str, Dict[int, xr.Dataset]] = {}  # region -> {hour -> dataset}
        
        # Use shared rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=settings.wind.rate_limit["requests_per_minute"],
            batch_size=settings.wind.rate_limit["batch_size"],
            batch_pause=settings.wind.rate_limit["batch_pause"]
        )
        
    def update_model_run(self, model_run: ModelRun):
        """Update the current model run and clean up old files."""
        logger.info(f"🔄 Updating wind client model run to: {model_run}")
        self.model_run = model_run
        self.file_storage.cleanup_old_files(model_run)
        self._is_initialized = False
        self._initialization_error = None
        self._datasets.clear()  # Clear cached datasets
        
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
            
            # Calculate how long the model run has been available
            hours_since_available = (datetime.now(timezone.utc) - self.model_run.available_time).total_seconds() / 3600
            
            # Determine maximum forecast hour based on availability time
            # GFS files are published progressively, with early forecast hours first
            # Typically, forecast hours up to ~120 are available within the first hour
            # Higher forecast hours become available over the next 1-2 hours
            max_forecast_hour = min(384, int(hours_since_available * 120))
            
            # Ensure we have at least some forecast hours (minimum 72 hours)
            max_forecast_hour = max(72, max_forecast_hour)
            
            # Filter forecast hours to only include those likely to be available
            available_forecast_hours = [h for h in self.forecast_hours if h <= max_forecast_hour]
            
            logger.info(
                f"Model run {self.model_run.date_str} {self.model_run.cycle_hour:02d}Z has been available for "
                f"{hours_since_available:.1f} hours. Using forecast hours up to {max_forecast_hour}"
            )
            
            initialization_errors = []
            
            # Initialize each region
            for region_name, region_config in settings.wind.regions.items():
                try:
                    logger.info(f"🌎 Initializing {region_name} region wind data...")
                    
                    # Get list of missing files but sort by forecast hour
                    missing_files = sorted(
                        self.file_storage.get_missing_files(
                            region_name,
                            self.model_run,
                            available_forecast_hours  # Use filtered forecast hours
                        ),
                        key=lambda x: x[0]  # Sort by forecast hour
                    )
                    
                    if missing_files:
                        logger.info(f"📥 Attempting to download {len(missing_files)} wind files for {region_name}...")
                        
                        # Calculate expected availability time for the first missing hour
                        first_hour = missing_files[0][0]
                        expected_time = self.model_run.available_time + timedelta(minutes=max(5, first_hour // 6))
                        
                        if datetime.now(timezone.utc) < expected_time:
                            wait_mins = (expected_time - datetime.now(timezone.utc)).total_seconds() / 60
                            logger.warning(
                                f"⚠️ First missing hour {first_hour} not expected until "
                                f"{expected_time.strftime('%H:%M:%S')} UTC "
                                f"(in ~{wait_mins:.1f} minutes)"
                            )
                        
                        downloaded, failed = await self._download_regional_files(region_name, missing_files)
                        
                        if downloaded == 0:
                            error_msg = f"Failed to download any wind files for {region_name}"
                            initialization_errors.append(error_msg)
                            logger.error(f"❌ {error_msg}")
                            continue
                            
                        logger.info(f"📊 {region_name} wind download summary: {downloaded} succeeded, {failed} failed")
                        
                        # If we have some successful downloads but not all, log a warning
                        if failed > 0:
                            logger.warning(
                                f"⚠️ Some forecast hours not yet available for {region_name} "
                                f"({failed} missing, will retry on next update)"
                            )
                    else:
                        logger.info(f"✨ All wind files already available for {region_name}")
                    
                    # Load the dataset with available files
                    valid_files = self.file_storage.get_valid_files(
                        region_name,
                        self.model_run,
                        available_forecast_hours  # Use filtered forecast hours
                    )
                    
                    if not valid_files:
                        error_msg = f"No valid wind files available for {region_name}"
                        initialization_errors.append(error_msg)
                        logger.error(f"❌ {error_msg}")
                        continue
                        
                    logger.info(f"🔄 Loading {len(valid_files)} wind files for {region_name}...")
                    
                    # Initialize region's dataset cache
                    self._datasets[region_name] = {}
                    
                    # Load each file into a dataset
                    loaded_files = 0
                    for file_path in valid_files:
                        try:
                            forecast_hour = int(str(file_path).split('_f')[-1].split('.')[0])
                            ds = xr.open_dataset(
                                file_path,
                                engine='cfgrib',
                                decode_timedelta=False,
                                backend_kwargs={'indexpath': ''}
                            )
                            self._datasets[region_name][forecast_hour] = ds
                            loaded_files += 1
                        except Exception as e:
                            logger.error(f"❌ Error loading wind file {file_path}: {str(e)}")
                            continue
                            
                    if loaded_files > 0:
                        logger.info(f"✅ Successfully loaded {loaded_files} wind files for {region_name}")
                    else:
                        error_msg = f"Failed to load any wind files for {region_name}"
                        initialization_errors.append(error_msg)
                        logger.error(f"❌ {error_msg}")
                        
                except Exception as e:
                    error_msg = f"Error initializing {region_name} wind data: {str(e)}"
                    initialization_errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    continue
            
            if initialization_errors and not any(self._datasets.values()):
                # Only fail initialization if we have no data at all
                self._initialization_error = "; ".join(initialization_errors)
                logger.error(f"❌ Wind initialization errors: {self._initialization_error}")
                raise HTTPException(
                    status_code=503,
                    detail=self._initialization_error
                )
            elif initialization_errors:
                # Log warning but continue if we have partial data
                logger.warning("⚠️ Wind initialization completed with some errors")
            
            self._is_initialized = True
            logger.info(
                f"✅ Wind client initialization complete with model run "
                f"{self.model_run.date_str} {self.model_run.cycle_hour:02d}Z"
            )

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
            
        for region_name, region_config in settings.wind.regions.items():
            bounds = region_config.grid
            if (bounds.lat.start <= lat <= bounds.lat.end and
                bounds.lon.start <= lon <= bounds.lon.end):
                return region_name
                
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
        if not self.model_run:
            raise ValueError("No model run available")
            
        region_config = settings.wind.regions[region]
        bounds = region_config.grid
        
        # Build the directory path and URL-encode it
        dir_path = f"/gfs.{self.model_run.date_str}/{self.model_run.cycle_hour:02d}/atmos"
        dir_path = dir_path.replace("/", "%2F")
        
        file_name = f"gfs.t{self.model_run.cycle_hour:02d}z.pgrb2.0p25.f{forecast_hour:03d}"
        
        params = {
            "file": file_name,
            "dir": dir_path,
            "subregion": "",
            "leftlon": str(bounds.lon.start),
            "rightlon": str(bounds.lon.end),
            "toplat": str(bounds.lat.end),
            "bottomlat": str(bounds.lat.start)
        }
        
        # Add variables and levels from config
        for var in region_config.variables:
            params[f"var_{var}"] = "on"
            
        for level in region_config.levels:
            params[f"lev_{level}"] = "on"
        
        # Build query string with sorted parameters for consistency
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        url = f"{settings.wind.base_url}?{query}"
        
        logger.info(
            f"Building URL for forecast hour {forecast_hour}:\n"
            f"  Base URL: {settings.wind.base_url}\n"
            f"  Model Run: {self.model_run.date_str} {self.model_run.cycle_hour:02d}Z\n"
            f"  File: {file_name}\n"
            f"  Region: {region} (lat: {bounds.lat.start}-{bounds.lat.end}, lon: {bounds.lon.start}-{bounds.lon.end})\n"
            f"  Full URL: {url}"
        )
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
            
            if region not in self._datasets:
                raise HTTPException(
                    status_code=503,
                    detail=f"No data available for region {region}"
                )
            
            forecasts: List[WindForecastPoint] = []
            total_hours = 0
            failed_hours = 0
            
            for hour in range(0, 385, 3):
                try:
                    if hour not in self._datasets[region]:
                        logger.warning(f"Missing dataset for hour {hour}")
                        failed_hours += 1
                        continue
                        
                    ds = self._datasets[region][hour]
                    wind_data = self._process_grib_data(ds, lat, lon)
                    
                    if wind_data:
                        valid_time, u, v, gust = wind_data
                        speed, direction = self._calculate_wind(u, v)
                        
                        # Ensure speed and gust are not None before conversion
                        speed_mph = UnitConversions.ms_to_mph(speed) if speed is not None else 0.0
                        gust_mph = UnitConversions.ms_to_mph(gust) if gust is not None else 0.0
                        
                        forecasts.append(WindForecastPoint(
                            time=valid_time,
                            speed=speed_mph,
                            direction=direction,
                            gust=gust_mph
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

    async def _fetch_content(self, url: str, timeout_seconds: int = 300) -> Optional[bytes]:
        """Simple helper to fetch content from URL, handling redirects."""
        try:
            async with aiohttp.ClientSession(
                cookies={'osCsid': 'dummy'},
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            ) as session:
                timeout = aiohttp.ClientTimeout(total=timeout_seconds)
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.error(f"Failed to fetch {url}: status {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def _rate_limit(self):
        """Apply rate limiting using the shared rate limiter."""
        await self.rate_limiter.limit()

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
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': '*/*'
                }
            ) as session:
                # Use ClientTimeout object for proper timeout handling
                timeout = aiohttp.ClientTimeout(total=300)
                logger.info(f"Attempting download from: {url}")
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.read()
                        content_size = len(content)
                        logger.info(f"Downloaded {content_size} bytes")
                        if content_size < 1000:  # Increased minimum size check
                            logger.error(f"Downloaded file too small ({content_size} bytes), likely error page")
                            return False
                        if await self.file_storage.save_file(file_path, content):
                            return True
                    else:
                        logger.error(f"Download failed with status {response.status}")
                        if response.status == 404:
                            try:
                                error_content = await response.text()
                                logger.error(f"404 response content: {error_content[:200]}...")  # Log first 200 chars
                            except Exception as e:
                                logger.error(f"Could not read error content: {str(e)}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return False
            
        return False  # Ensure we always return a bool

    async def _download_regional_files(
        self,
        region: str,
        missing_files: List[Tuple[int, Path]]
    ) -> Tuple[int, int]:
        """Download missing files for a region."""
        downloaded = failed = 0
        skipped = 0
        
        logger.info(f"Starting download of {len(missing_files)} files for {region}")
        
        # Group files by forecast hour ranges for better logging
        hour_ranges = {
            "0-24": [], "24-48": [], "48-72": [], "72-120": [], 
            "120-240": [], "240-384": []
        }
        
        for forecast_hour, file_path in missing_files:
            if forecast_hour <= 24:
                hour_ranges["0-24"].append((forecast_hour, file_path))
            elif forecast_hour <= 48:
                hour_ranges["24-48"].append((forecast_hour, file_path))
            elif forecast_hour <= 72:
                hour_ranges["48-72"].append((forecast_hour, file_path))
            elif forecast_hour <= 120:
                hour_ranges["72-120"].append((forecast_hour, file_path))
            elif forecast_hour <= 240:
                hour_ranges["120-240"].append((forecast_hour, file_path))
            else:
                hour_ranges["240-384"].append((forecast_hour, file_path))
                
        # Log the distribution of files by hour range
        for range_name, files in hour_ranges.items():
            if files:
                logger.info(f"Range {range_name} hours: {len(files)} files to download")
        
        # Track consecutive failures to detect patterns
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        for forecast_hour, file_path in missing_files:
            # Skip forecast hours that are likely not available yet
            if not self.model_run:
                continue
                
            # Calculate the expected availability time for this forecast hour
            # GFS files become available progressively, with early hours first
            expected_time = self.model_run.available_time + timedelta(minutes=max(5, forecast_hour // 6))
            current_time = datetime.now(timezone.utc)
            
            if current_time < expected_time:
                logger.info(
                    f"⏳ Skipping forecast hour {forecast_hour}, not expected until "
                    f"{expected_time.strftime('%H:%M:%S')} UTC "
                    f"(in {(expected_time - current_time).total_seconds() / 60:.1f} minutes)"
                )
                skipped += 1
                continue
                
            # Log attempt with timing info
            logger.info(
                f"📥 Attempting forecast hour {forecast_hour} "
                f"(expected since {expected_time.strftime('%H:%M:%S')} UTC, "
                f"current time {current_time.strftime('%H:%M:%S')} UTC)"
            )
                
            url = self._build_grib_filter_url(forecast_hour, region)
            if await self._download_grib_file(url, file_path):
                downloaded += 1
                consecutive_failures = 0  # Reset consecutive failures counter
            else:
                failed += 1
                consecutive_failures += 1
                
                # If we've had too many consecutive failures, skip ahead to avoid wasting time
                if consecutive_failures >= max_consecutive_failures:
                    next_range_start = (forecast_hour // 24 + 1) * 24  # Skip to next day's worth of forecasts
                    logger.warning(
                        f"⚠️ {consecutive_failures} consecutive failures detected. "
                        f"Skipping ahead to forecast hour {next_range_start}"
                    )
                    
                    # Find the next forecast hour to try
                    next_files = [(h, p) for h, p in missing_files if h >= next_range_start]
                    if next_files:
                        # Skip to the next range
                        forecast_hour, file_path = next_files[0]
                        consecutive_failures = 0
                    else:
                        # No more files to try in higher ranges
                        logger.warning("No more files to try in higher forecast ranges")
                        break
                
            # Respect rate limit between downloads
            await self._rate_limit()
                
        logger.info(
            f"Download summary for {region}:\n"
            f"  - Downloaded: {downloaded}\n"
            f"  - Failed: {failed}\n"
            f"  - Skipped (not yet available): {skipped}\n"
            f"  - Total files needed: {len(missing_files)}"
        )
                
        return downloaded, failed 