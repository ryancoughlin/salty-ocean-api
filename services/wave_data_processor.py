import xarray as xr
import numpy
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import time

from models.grib import Grib2File
from repositories.station_repo import StationRepository
from utils.grid import GridUtils
from services.wave_data_downloader import WaveDataDownloader
from core.config import settings

logger = logging.getLogger(__name__)

class WaveDataProcessor:
    def __init__(self):
        """Initialize wave data processor."""
        self.station_repo = StationRepository(Path('ndbcStations.json'))
        self.downloader = WaveDataDownloader()

    def get_current_model_run(self) -> tuple[str, str]:
        """Get current model run information from the downloader."""
        return self.downloader.get_current_model_run()

    def get_forecast_timestamp(self, forecast_hour: int) -> str:
        """Get ISO timestamp for forecast hour."""
        return (datetime.utcnow() + timedelta(hours=forecast_hour)).isoformat()

    def process_grib_file(self, file_path: Path, lat: float, lon: float) -> Optional[Dict]:
        """Process a single GRIB2 file and extract forecast data."""
        try:
            logger.debug(f"\nProcessing GRIB2 file: {file_path.name}")
            grib_file = Grib2File(file_path)
            
            region = 'atlantic' if lon > -100 else 'pacific'
            grid_config = settings.models[region]["grid"]
            lat_idx, lon_idx = grib_file.get_grid_indices(lat, lon, grid_config)
            
            # Extract all variables
            forecast = {
                'timestamp': self.get_forecast_timestamp(grib_file.forecast_hour),
                'grid_point': {
                    'latitude': float(grib_file.dataset.latitude[lat_idx].item()),
                    'longitude': float(grib_file.dataset.longitude[lon_idx].item())
                }
            }

            # Wind data
            wind_speed = grib_file.get_value_at_indices('ws', lat_idx, lon_idx)
            wind_dir = grib_file.get_value_at_indices('wdir', lat_idx, lon_idx)
            forecast['wind'] = {
                'speed': round(float(wind_speed), 2) if wind_speed is not None and not numpy.isnan(wind_speed) else None,
                'direction': round(float(wind_dir), 2) if wind_dir is not None and not numpy.isnan(wind_dir) else None,
                'units': {
                    'speed': 'm/s',
                    'direction': 'degrees'
                }
            }

            # Wave data
            wave_height = grib_file.get_value_at_indices('swh', lat_idx, lon_idx)
            wave_period = grib_file.get_value_at_indices('perpw', lat_idx, lon_idx)
            wave_dir = grib_file.get_value_at_indices('dirpw', lat_idx, lon_idx)
            forecast['waves'] = {
                'height': round(float(wave_height), 2) if wave_height is not None and not numpy.isnan(wave_height) else None,
                'period': round(float(wave_period), 2) if wave_period is not None and not numpy.isnan(wave_period) else None,
                'direction': round(float(wave_dir), 2) if wave_dir is not None and not numpy.isnan(wave_dir) else None,
                'units': {
                    'height': 'm',
                    'period': 's',
                    'direction': 'degrees'
                }
            }

            # Wind wave data
            wind_wave_height = grib_file.get_value_at_indices('shww', lat_idx, lon_idx)
            wind_wave_period = grib_file.get_value_at_indices('mpww', lat_idx, lon_idx)
            wind_wave_dir = grib_file.get_value_at_indices('wvdir', lat_idx, lon_idx)
            forecast['wind_waves'] = {
                'height': round(float(wind_wave_height), 2) if wind_wave_height is not None and not numpy.isnan(wind_wave_height) else None,
                'period': round(float(wind_wave_period), 2) if wind_wave_period is not None and not numpy.isnan(wind_wave_period) else None,
                'direction': round(float(wind_wave_dir), 2) if wind_wave_dir is not None and not numpy.isnan(wind_wave_dir) else None,
                'units': {
                    'height': 'm',
                    'period': 's',
                    'direction': 'degrees'
                }
            }

            # Swell data
            swell_height = grib_file.get_value_at_indices('shts', lat_idx, lon_idx)
            swell_period = grib_file.get_value_at_indices('mpts', lat_idx, lon_idx)
            swell_dir = grib_file.get_value_at_indices('swdir', lat_idx, lon_idx)
            forecast['swell'] = {
                'height': round(float(swell_height), 2) if swell_height is not None and not numpy.isnan(swell_height) else None,
                'period': round(float(swell_period), 2) if swell_period is not None and not numpy.isnan(swell_period) else None,
                'direction': round(float(swell_dir), 2) if swell_dir is not None and not numpy.isnan(swell_dir) else None,
                'units': {
                    'height': 'm',
                    'period': 's',
                    'direction': 'degrees'
                }
            }

            grib_file.close()
            return forecast
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {str(e)}")
            return None

    def get_scalar_value(self, dataset, var_name, lat_i, lon_i):
        """Safely extract a scalar value from the dataset."""
        if var_name not in dataset:
            logger.debug(f"Variable {var_name} not found in dataset")
            return None
        try:
            # Get the DataArray for the variable
            da = dataset[var_name]
            
            # Log the shape and coordinates
            logger.debug(f"Variable {var_name} shape: {da.shape}")
            logger.debug(f"Variable {var_name} coords: {list(da.coords)}")
            
            # For swell variables with orderedSequenceData dimension, select first component
            if 'orderedSequenceData' in da.dims:
                da = da.isel(orderedSequenceData=0)
                logger.debug(f"Selected first swell component for {var_name}")
            
            # Select the point using isel for positional indexing
            point_data = da.isel(latitude=lat_i, longitude=lon_i)
            
            # Handle any remaining dimensions by taking first value
            for dim in point_data.dims:
                if dim not in ['latitude', 'longitude']:
                    point_data = point_data.isel({dim: 0})
            
            # Ensure we have a scalar value
            if point_data.size != 1:
                logger.warning(f"Expected scalar value for {var_name} but got array of size {point_data.size}")
                return None
                
            # Convert to a numpy array and then to a Python scalar
            value = float(point_data.values.item())
            logger.debug(f"Extracted {var_name} value: {value}")
            return value
        
        except Exception as e:
            logger.error(f"Error extracting {var_name}: {str(e)}")
            logger.debug(f"Full error details for {var_name}:", exc_info=True)
            return None

    def normalize_longitude(self, lon: float) -> float:
        """Convert longitude to 0-360 format."""
        return lon + 360 if lon < 0 else lon

    def process_station_forecast(self, station_id: str, model_run: str = None, date: str = None) -> Dict:
        """Process all forecast files for a station."""
        start_time = time.time()
        
        # Get station coordinates
        coords = self.station_repo.get_station_coordinates(station_id)
        if not coords:
            raise ValueError(f"Station {station_id} not found")
            
        lon, lat = coords
        logger.info(f"Processing forecast for station {station_id} at lat={lat}, lon={lon}")

        # Get current model run if not provided
        if model_run is None or date is None:
            model_run, date = self.get_current_model_run()
            logger.info(f"Using current model run: {date} {model_run}z")
        
        # Determine region based on longitude
        region = 'pacific' if lon <= -100 else 'atlantic'
        model_name = settings.models[region]["name"]
        grid_config = settings.models[region]["grid"]
        logger.info(f"Using {region} region model: {model_name}")
        
        # Normalize longitude to 0-360 format for grid calculations
        normalized_lon = self.normalize_longitude(lon)
        
        # Process each forecast hour following NOAA's pattern (3-hourly from 120 to 384)
        hours = settings.forecast_hours
        logger.info(f"Processing forecast hours {min(hours)} to {max(hours)} every 3 hours")
        
        # Build list of files to process
        files = []
        for hour in hours:  # This ensures we only process files for our forecast hours
            file_name = f"gfswave.t{model_run}z.{model_name}.f{str(hour).zfill(3)}.grib2"
            file_path = Path(settings.data_dir) / file_name
            if file_path.exists():
                files.append(str(file_path))
            else:
                logger.warning(f"Missing forecast file for hour {hour}: {file_name}")
        
        if not files:
            logger.error("No GRIB2 files found")
            raise ValueError("No forecast data available")
            
        logger.info(f"Found {len(files)} forecast files to process")
        
        try:
            # Open first file to get grid information
            first_ds = xr.open_dataset(files[0], engine='cfgrib', backend_kwargs={'indexpath': ''})
            
            # Find nearest grid point
            lat_diffs = abs(first_ds.latitude - lat)
            ds_lons = first_ds.longitude.values
            ds_lons = numpy.where(ds_lons < 0, ds_lons + 360, ds_lons)
            lon_diffs = abs(ds_lons - normalized_lon)
            
            lat_idx = int(lat_diffs.argmin().values)
            lon_idx = int(lon_diffs.argmin())
            
            # Get actual grid point coordinates
            grid_lat = float(first_ds.latitude[lat_idx].values)
            grid_lon = float(first_ds.longitude[lon_idx].values)
            if grid_lon < 0:
                grid_lon += 360
            
            # Check if grid point is too far from station
            lat_diff = abs(grid_lat - lat)
            lon_diff = abs(grid_lon - normalized_lon)
            if lat_diff > 1.0 or lon_diff > 1.0:  # More than 1 degree difference
                logger.error(f"Nearest grid point too far from station: lat_diff={lat_diff:.4f}°, lon_diff={lon_diff:.4f}°")
                raise ValueError("No forecast data available - station location outside model grid")
            
            logger.info(f"Using grid point: lat={grid_lat}, lon={grid_lon}")
            first_ds.close()
            
            # Process each file using the same grid indices
            forecasts = []
            for hour, file_path in zip(hours, files):
                process_start = time.time()
                try:
                    ds = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={'indexpath': ''})
                    
                    forecast = {
                        'timestamp': self.get_forecast_timestamp(hour),
                        'grid_point': {
                            'latitude': grid_lat,
                            'longitude': lon  # Use original longitude format
                        }
                    }
                    
                    # Extract wind data
                    wind_speed = self.get_scalar_value(ds, 'ws', lat_idx, lon_idx)
                    wind_dir = self.get_scalar_value(ds, 'wdir', lat_idx, lon_idx)
                    if wind_speed is not None and not numpy.isnan(wind_speed):
                        forecast['wind'] = {
                            'speed': round(wind_speed, 2),
                            'direction': round(wind_dir, 2) if wind_dir is not None and not numpy.isnan(wind_dir) else None,
                            'units': {'speed': 'm/s', 'direction': 'degrees'}
                        }
                    
                    # Extract wave data
                    wave_height = self.get_scalar_value(ds, 'swh', lat_idx, lon_idx)
                    wave_period = self.get_scalar_value(ds, 'perpw', lat_idx, lon_idx)
                    wave_dir = self.get_scalar_value(ds, 'dirpw', lat_idx, lon_idx)
                    if wave_height is not None and not numpy.isnan(wave_height):
                        forecast['waves'] = {
                            'height': round(wave_height, 2),
                            'period': round(wave_period, 2) if wave_period is not None and not numpy.isnan(wave_period) else None,
                            'direction': round(wave_dir, 2) if wave_dir is not None and not numpy.isnan(wave_dir) else None,
                            'units': {'height': 'm', 'period': 's', 'direction': 'degrees'}
                        }
                    
                    # Extract wind wave data
                    wind_wave_height = self.get_scalar_value(ds, 'shww', lat_idx, lon_idx)
                    wind_wave_period = self.get_scalar_value(ds, 'mpww', lat_idx, lon_idx)
                    wind_wave_dir = self.get_scalar_value(ds, 'wvdir', lat_idx, lon_idx)
                    if wind_wave_height is not None and not numpy.isnan(wind_wave_height):
                        forecast['wind_waves'] = {
                            'height': round(wind_wave_height, 2),
                            'period': round(wind_wave_period, 2) if wind_wave_period is not None and not numpy.isnan(wind_wave_period) else None,
                            'direction': round(wind_wave_dir, 2) if wind_wave_dir is not None and not numpy.isnan(wind_wave_dir) else None,
                            'units': {'height': 'm', 'period': 's', 'direction': 'degrees'}
                        }
                    
                    # Extract swell data
                    swell_height = self.get_scalar_value(ds, 'shts', lat_idx, lon_idx)
                    swell_period = self.get_scalar_value(ds, 'mpts', lat_idx, lon_idx)
                    swell_dir = self.get_scalar_value(ds, 'swdir', lat_idx, lon_idx)
                    if swell_height is not None and not numpy.isnan(swell_height):
                        forecast['swell'] = {
                            'height': round(swell_height, 2),
                            'period': round(swell_period, 2) if swell_period is not None and not numpy.isnan(swell_period) else None,
                            'direction': round(swell_dir, 2) if swell_dir is not None and not numpy.isnan(swell_dir) else None,
                            'units': {'height': 'm', 'period': 's', 'direction': 'degrees'}
                        }
                    
                    if len(forecast) > 2:  # More than just timestamp and grid_point
                        forecasts.append(forecast)
                        
                    ds.close()
                    process_time = time.time() - process_start
                    logger.debug(f"Processed hour {hour} in {process_time:.2f}s")
                    
                except Exception as e:
                    logger.error(f"Error processing hour {hour}: {str(e)}")
                    continue
            
            total_time = time.time() - start_time
            logger.info(f"Processed {len(forecasts)} forecasts in {total_time:.2f}s")
            
            return {
                "metadata": {
                    "station": {
                        "id": station_id,
                        "location": {
                            "latitude": lat,
                            "longitude": lon
                        }
                    },
                    "model": {
                        "name": "GFS-Wave WAVEWATCH III",
                        "run": model_run,
                        "date": date,
                        "region": region
                    },
                    "units": {
                        "wind_speed": "m/s",
                        "wave_height": "m",
                        "period": "s",
                        "direction": "degrees"
                    }
                },
                "forecasts": forecasts
            }
            
        except Exception as e:
            logger.error(f"Error processing GRIB2 files: {str(e)}")
            return {"forecasts": []}

    def determine_region(self, lon: float, lat: float) -> Optional[str]:
        """Determine which model region contains the given coordinates."""
        # Convert longitude to 0-360 format if needed
        normalized_lon = self.normalize_longitude(lon)
        
        logger.info(f"\nChecking region for coordinates: lat={lat}, lon={lon}")
        logger.info(f"Normalized longitude: {normalized_lon}")
        
        for region, config in settings.models.items():
            grid = config["grid"]
            logger.info(f"\nChecking {region} region boundaries:")
            logger.info(f"Latitude:  {grid['lat']['start']} to {grid['lat']['end']}")
            logger.info(f"Longitude: {grid['lon']['start']} to {grid['lon']['end']}")
            
            # Convert grid boundaries to 0-360 format if needed
            grid_lon_start = self.normalize_longitude(grid["lon"]["start"])
            grid_lon_end = self.normalize_longitude(grid["lon"]["end"])
            
            lat_in_bounds = grid["lat"]["start"] <= lat <= grid["lat"]["end"]
            
            # Handle cases where the region crosses the 180/-180 boundary
            if grid_lon_start > grid_lon_end:
                lon_in_bounds = normalized_lon >= grid_lon_start or normalized_lon <= grid_lon_end
            else:
                lon_in_bounds = grid_lon_start <= normalized_lon <= grid_lon_end
            
            logger.info(f"Latitude in bounds: {lat_in_bounds}")
            logger.info(f"Longitude in bounds: {lon_in_bounds}")
            
            if lat_in_bounds and lon_in_bounds:
                logger.info(f"Found matching region: {region}")
                return region
                
        logger.warning(
            f"No region found for coordinates: lat={lat}, lon={lon} "
            f"(normalized lon={normalized_lon})"
        )
        return None 

    async def update_model_data(self):
        """Update wave model data for the current run."""
        try:
            model_run, date = self.get_current_model_run()
            logger.info(f"Updating wave model data for {date} {model_run}z")
            
            success = await self.downloader.download_model_data()
            if not success:
                raise Exception("Failed to download wave model data")
                
            logger.info("Wave model data updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating wave model data: {str(e)}")
            return False

    def has_current_data(self) -> bool:
        """Check if we have data for the current model run."""
        try:
            model_run, date = self.get_current_model_run()
            return self.downloader.has_current_data()
        except Exception:
            return False 