import logging
import aiohttp
import xarray as xr
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import asyncio
from fastapi import HTTPException

from features.common.models.station_types import Station
from features.common.utils.conversions import UnitConversions
from core.config import settings
from core.cache import cached
from features.common.model_run import ModelRun
from features.waves.services.file_storage import GFSWaveFileStorage

logger = logging.getLogger(__name__)

class WaveDataPoint(BaseModel):
    """Single point of wave data from GRIB file with known types."""
    height: float = Field(..., ge=0, description="Significant wave height in meters")
    period: float = Field(..., ge=0, description="Wave period in seconds")
    direction: float = Field(..., ge=0, lt=360, description="Wave direction in degrees true")

class GFSWaveComponent(BaseModel):
    """Individual wave component in GFS forecast."""
    height_m: float = Field(..., ge=0, description="Wave height in meters")
    height_ft: float = Field(..., ge=0, description="Wave height in feet")
    period: float = Field(..., ge=0, description="Wave period in seconds")
    direction: float = Field(..., ge=0, lt=360, description="Wave direction in degrees")

class GFSForecastPoint(BaseModel):
    """Single point in GFS wave forecast."""
    timestamp: datetime = Field(..., description="Forecast timestamp in UTC")
    waves: List[GFSWaveComponent] = Field(..., description="Wave components sorted by height")

class GFSModelCycle(BaseModel):
    """GFS model run information."""
    date: str = Field(..., description="Model run date in YYYYMMDD format")
    hour: str = Field(..., description="Model run hour in HH format (UTC)")

class GFSWaveForecast(BaseModel):
    """Complete GFS wave forecast for a station."""
    station_info: Station
    cycle: GFSModelCycle
    forecasts: List[GFSForecastPoint]

CACHE_DIR = Path(settings.cache_dir) / "gfs_wave"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class GFSWaveClient:
    def __init__(self, model_run: Optional[ModelRun] = None):
        self._session: Optional[aiohttp.ClientSession] = None
        self.model_run = model_run
        self._regional_datasets: Dict[str, xr.Dataset] = {}
        self._is_initialized = False
        self.file_storage = GFSWaveFileStorage()
        # Get regions from config
        self.regions = list(settings.models.keys())
        # Get forecast hours from config and create list
        self.forecast_hours = list(range(0, settings.forecast_hours + 1, 3))  # 0 to max by 3-hour steps
        
    def update_model_run(self, model_run: ModelRun):
        """Update the current model run."""
        self.model_run = model_run
        # Clear cached datasets when model run changes
        self._regional_datasets.clear()
        
    async def initialize(self):
        """Initialize the wave client by loading the latest model run data."""
        if not self.model_run:
            raise HTTPException(
                status_code=503,
                detail="No model cycle currently available"
            )
            
        # Initialize each configured region
        for region in self.regions:
            # Check if we have a cached dataset
            cycle_key = f"{region}_{self.model_run.run_date.strftime('%Y%m%d')}_{self.model_run.cycle_hour:02d}"
            
            if cycle_key in self._regional_datasets:
                continue

            try:
                file_paths = await self._download_regional_files(
                    self.model_run.run_date,
                    f"{self.model_run.cycle_hour:02d}",
                    region
                )
                if not file_paths:
                    logger.error(f"No data files available for {region}")
                    continue
                    
                # Load the dataset
                ds = await self._load_grib_files(
                    region,
                    self.model_run.run_date,
                    f"{self.model_run.cycle_hour:02d}"
                )
                if ds is not None:
                    self._regional_datasets[cycle_key] = ds
                else:
                    logger.error(f"Failed to load dataset for {region}")
                    continue
                    
            except Exception as e:
                logger.error(f"Error loading dataset for {region}: {str(e)}")
                continue
        
        self._is_initialized = True

    async def _init_session(self) -> aiohttp.ClientSession:
        """Initialize or return existing aiohttp session."""
        if not self._session or self._session.closed:
            # Create cookie jar and session with redirect handling
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(
                cookie_jar=cookie_jar,
                timeout=aiohttp.ClientTimeout(total=300),
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
            )
        return self._session
        
    async def close(self):
        """Close the aiohttp session and cleanup datasets."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        # Close any open datasets
        for ds in self._regional_datasets.values():
            ds.close()
        self._regional_datasets.clear()

    def _get_region_for_station(self, lat: float, lon: float) -> str:
        """Determine region based on station coordinates."""
        # Convert longitude to -180 to 180 format if it's not already
        lon = lon if -180 <= lon <= 180 else (lon - 360 if lon > 180 else lon)
        
        # Atlantic region: -100 to -50 degrees longitude
        if -100 <= lon <= -50:
            return "atlantic"
            
        return "pacific"

    def _get_grib_file_path(
        self,
        region: str,
        cycle_date: datetime,
        cycle_hour: str,
        forecast_hour: int
    ) -> Path:
        """Get the path for a GRIB file."""
        return CACHE_DIR / f"{region}_gfs_{cycle_date.strftime('%Y%m%d')}_{cycle_hour}z_f{forecast_hour:03d}.grib2"

    def _is_file_valid(self, file_path: Path) -> bool:
        """Check if a file exists and is valid (non-empty and recent)."""
        if not file_path.exists():
            return False
            
        # Check file size
        if file_path.stat().st_size < 100:  # Minimum size in bytes
            return False
            
        # Check file age (4 hours max)
        file_age = datetime.now(timezone.utc) - datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
        if file_age > timedelta(hours=4):
            return False
            
        return True

    def _build_grib_filter_url(
        self,
        cycle_date: datetime,
        cycle_hour: str,
        forecast_hour: int,
        region: str
    ) -> str:
        """Build a GRIB filter URL for a region."""
        # Get region config
        region_config = settings.models[region]
        product = region_config["name"]
        
        # Build params in the exact order expected by NOAA
        params = [
            ("file", f"gfswave.t{cycle_hour}z.{product}.f{forecast_hour:03d}.grib2"),
            ("lev_surface", "on"),
            ("var_DIRPW", "on"),
            ("var_HTSGW", "on"),
            ("var_PERPW", "on"),
            ("dir", f"/gfs.{cycle_date.strftime('%Y%m%d')}/{cycle_hour}/wave/gridded")
        ]
        
        query = "&".join(f"{k}={v}" for k, v in params)
        url = f"{settings.gfs_wave_filter_url}/filter_gfswave.pl?{query}"
        logger.debug(f"Built URL for {region} f{forecast_hour:03d}: {url}")
        return url

    async def _download_grib_file(
        self,
        url: str,
        file_path: Path
    ) -> Optional[Path]:
        """Download a GRIB file and save it to the specified path."""
        try:
            session = await self._init_session()
            
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    logger.error(f"Download failed with status {response.status}")
                    if response.status == 302:
                        location = response.headers.get('Location')
                        logger.error(f"Redirect location: {location}")
                    return None
                    
                content = await response.read()
                content_size = len(content)
                
                if content_size < 100:
                    logger.error(f"Downloaded file too small: {content_size} bytes")
                    return None
                    
                if await self.file_storage.save_file(file_path, content):
                    return file_path
                return None
                
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None

    async def _download_regional_files(
        self,
        cycle_date: datetime,
        cycle_hour: str,
        region: str
    ) -> List[Path]:
        """Download missing forecast files for a region."""
        try:
            # Get list of missing files
            missing_files = self.file_storage.get_missing_files(
                region,
                cycle_date,
                cycle_hour,
                self.forecast_hours
            )
            
            if not missing_files:
                logger.info("Files already available for %s", region)
                return self.file_storage.get_valid_files(
                    region,
                    cycle_date,
                    cycle_hour,
                    self.forecast_hours
                )

            downloaded = 0
            failed = 0
            
            for forecast_hour, file_path in missing_files:
                url = self._build_grib_filter_url(cycle_date, cycle_hour, forecast_hour, region)
                result = await self._download_grib_file(url, file_path)
                if result:
                    downloaded += 1
                else:
                    failed += 1
                    
            if downloaded > 0:
                logger.info(
                    f"Region {region} download summary:\n"
                    f"  - Files needed: {len(missing_files)}\n"
                    f"  - Downloaded: {downloaded}\n"
                    f"  - Failed: {failed}"
                )
            
            # Return all valid files including previously downloaded ones
            return self.file_storage.get_valid_files(
                region,
                cycle_date,
                cycle_hour,
                self.forecast_hours
            )
            
        except Exception as e:
            logger.error(f"Error downloading files for {region}: {str(e)}")
            raise

    def _load_and_combine_dataset(self, file_paths: List[Path]) -> xr.Dataset:
        """Load and combine GRIB files into a single dataset."""
        datasets = []
        
        for fp in file_paths:
            try:
                if not fp.exists():
                    logger.error(f"File not found: {fp}")
                    continue
                    
                # Load GRIB file with explicit datetime decoding settings
                ds = xr.open_dataset(
                    fp,
                    engine="cfgrib",
                    backend_kwargs={
                        'indexpath': '',
                        'use_cftime': False,
                        'decode_times': True,
                        'decode_timedelta': False
                    }
                )
                
                # Use valid_time as the time coordinate
                valid_time = pd.to_datetime(ds.valid_time.values)
                ds = ds.assign_coords(time=valid_time)
                
                datasets.append(ds)
                
            except Exception as e:
                logger.error(f"Error loading {fp}: {str(e)}")
                continue
                
        if not datasets:
            logger.error("No valid datasets were loaded")
            raise Exception("No valid datasets were loaded")
            
        # Combine datasets along time dimension
        combined_ds = xr.concat(datasets, dim="time")
        
        # Sort by time to ensure forecast sequence
        return combined_ds.sortby("time")

    async def _load_grib_files(
        self,
        region: str,
        cycle_date: datetime,
        cycle_hour: str
    ) -> Optional[xr.Dataset]:
        """Load GRIB files for a region and combine them into a single dataset."""
        try:
            # Get all GRIB files for this cycle
            file_paths = []
            for hour in self.forecast_hours:
                file_path = self._get_grib_file_path(region, cycle_date, cycle_hour, hour)
                if file_path.exists():
                    file_paths.append(file_path)
                    
            if not file_paths:
                logger.error(f"No GRIB files found for {region}")
                return None
                
            # Load and combine the datasets
            return self._load_and_combine_dataset(file_paths)
            
        except Exception as e:
            logger.error(f"Error loading GRIB files for {region}: {str(e)}")
            return None

    async def _prepare_regional_dataset(
        self,
        region: str,
        cycle_date: datetime,
        cycle_hour: str
    ) -> xr.Dataset:
        """Get the regional dataset that was prepared at startup."""
        cache_key = f"{region}_{cycle_date.strftime('%Y%m%d')}_{cycle_hour}"
        
        if not self._is_initialized:
            raise HTTPException(
                status_code=503,
                detail="Wave service not initialized"
            )
        
        if cache_key not in self._regional_datasets:
            raise HTTPException(
                status_code=503,
                detail=f"No data available for region {region}"
            )
            
        return self._regional_datasets[cache_key]

    def _extract_station_forecast(
        self,
        dataset: xr.Dataset,
        lat: float,
        lon: float
    ) -> List[GFSForecastPoint]:
        """Extract forecast for a specific station from regional dataset."""
        try:
            # Convert to 0-360 longitude (we know dataset uses this)
            query_lon = lon + 360 if lon < 0 else lon
            
            # Get nearest point data
            point_data = dataset.sel(
                latitude=lat, 
                longitude=query_lon, 
                method="nearest"
            )

            # Extract forecasts
            forecasts = []
            for t in point_data.time.values:
                time_data = point_data.sel(time=t)
                
                try:
                    # Extract known data types
                    wave_data = WaveDataPoint(
                        height=time_data.swh.item(),
                        period=time_data.perpw.item(),
                        direction=time_data.dirpw.item()
                    )
                    
                    # Create forecast point
                    wave_component = GFSWaveComponent(
                        height_m=wave_data.height,
                        height_ft=UnitConversions.meters_to_feet(wave_data.height),
                        period=wave_data.period,
                        direction=wave_data.direction
                    )
                    
                    forecasts.append(GFSForecastPoint(
                        timestamp=pd.Timestamp(t).tz_localize('UTC'),
                        waves=[wave_component]
                    ))
                    
                except ValueError as e:
                    continue
            
            if not forecasts:
                logger.warning(
                    f"No valid forecast points found for station at "
                    f"lat={lat:.3f}, lon={lon:.3f}"
                )
            
            return sorted(forecasts, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"Error extracting forecast: {str(e)}")
            raise

    async def get_station_forecast(self, station_id: str, station: Station) -> GFSWaveForecast:
        """Get wave forecast for a specific station."""
        try:
            if not self.model_run:
                raise HTTPException(
                    status_code=503,
                    detail="No model cycle currently available"
                )
                
            # Get station coordinates
            lat = station.location.coordinates[1]
            lon = station.location.coordinates[0]
            
            # Determine region and get dataset
            region = self._get_region_for_station(lat, lon)
            
            # Prepare dataset for this region if needed
            dataset = await self._prepare_regional_dataset(
                region,
                self.model_run.run_date,
                f"{self.model_run.cycle_hour:02d}"
            )
            
            # Extract forecast
            forecasts = self._extract_station_forecast(dataset, lat, lon)
            
            # Return forecast even if empty - let the service layer handle this
            return GFSWaveForecast(
                station_info=station,
                cycle=GFSModelCycle(
                    date=self.model_run.run_date.strftime("%Y%m%d"),
                    hour=f"{self.model_run.cycle_hour:02d}"
                ),
                forecasts=forecasts
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wave forecast: {str(e)}"
            )
            
        finally:
            await self.close() 