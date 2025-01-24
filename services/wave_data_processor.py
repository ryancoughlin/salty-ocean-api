import xarray as xr
import numpy as np
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from models.grib import Grib2File
from repositories.station_repo import StationRepository
from utils.grid import GridUtils
from services.wave_data_downloader import WaveDataDownloader
from core.config import settings

logger = logging.getLogger(__name__)

class WaveDataProcessor:
    def __init__(self):
        """Initialize wave data processor."""
        self.var_mapping = {
            'ws': 'wind_speed',
            'wdir': 'wind_direction',
            'swh': 'wave_height',
            'perpw': 'wave_period',
            'dirpw': 'wave_direction',
            'shww': 'wind_wave_height',
            'mpww': 'wind_wave_period',
            'wvdir': 'wind_wave_direction',
            'shts': 'swell_height',
            'mpts': 'swell_period',
            'swdir': 'swell_direction'
        }
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
            grib_file = Grib2File(file_path)
            region = 'atlantic' if lon > -100 else 'pacific'
            grid_config = settings.models[region]["grid"]
            lat_idx, lon_idx = grib_file.get_grid_indices(lat, lon, grid_config)
            
            # Extract all variables
            forecast = {}
            
            # Wind data
            wind_speed = grib_file.get_value_at_indices('ws', lat_idx, lon_idx)
            wind_dir = grib_file.get_value_at_indices('wdir', lat_idx, lon_idx)
            if wind_speed is not None:
                forecast['wind'] = {
                    'speed': round(wind_speed, 2),
                    'direction': round(wind_dir, 2) if wind_dir is not None else None,
                    'units': {
                        'speed': 'm/s',
                        'direction': 'degrees'
                    }
                }
            
            # Wave data
            wave_height = grib_file.get_value_at_indices('swh', lat_idx, lon_idx)
            wave_period = grib_file.get_value_at_indices('perpw', lat_idx, lon_idx)
            wave_dir = grib_file.get_value_at_indices('dirpw', lat_idx, lon_idx)
            if wave_height is not None:
                forecast['waves'] = {
                    'height': round(wave_height, 2),
                    'period': round(wave_period, 2) if wave_period is not None else None,
                    'direction': round(wave_dir, 2) if wave_dir is not None else None,
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
            if wind_wave_height is not None:
                forecast['wind_waves'] = {
                    'height': round(wind_wave_height, 2),
                    'period': round(wind_wave_period, 2) if wind_wave_period is not None else None,
                    'direction': round(wind_wave_dir, 2) if wind_wave_dir is not None else None,
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
            if swell_height is not None:
                forecast['swell'] = {
                    'height': round(swell_height, 2),
                    'period': round(swell_period, 2) if swell_period is not None else None,
                    'direction': round(swell_dir, 2) if swell_dir is not None else None,
                    'units': {
                        'height': 'm',
                        'period': 's',
                        'direction': 'degrees'
                    }
                }
            
            # Add timestamp and grid point info
            forecast['timestamp'] = self.get_forecast_timestamp(grib_file.forecast_hour)
            forecast['grid_point'] = {
                'latitude': float(grib_file.dataset.latitude[lat_idx].item()),
                'longitude': float(grib_file.dataset.longitude[lon_idx].item())
            }
            
            grib_file.close()
            return forecast
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            return None

    def process_station_forecast(self, station_id: str, model_run: str = None, date: str = None) -> Dict:
        """Process all forecast files for a station."""
        # Get station coordinates
        coords = self.station_repo.get_station_coordinates(station_id)
        if not coords:
            raise ValueError(f"Station {station_id} not found")
            
        lon, lat = coords  # Unpack the tuple directly
        logger.info(f"Processing forecasts for station {station_id} at {lat}, {lon}")

        # Get current model run if not provided
        if model_run is None or date is None:
            model_run, date = self.get_current_model_run()
            logger.info(f"Using current model run: {date} {model_run}z")
        
        # Determine region based on longitude
        region = 'pacific' if lon <= -100 else 'atlantic'
        model_name = settings.models[region]["name"]
        logger.info(f"Using {region} region model: {model_name}")
        
        forecasts = []
        
        # Process each forecast hour following NOAA's pattern
        hours = list(range(0, 121))  # 0-120 hourly
        hours.extend(range(121, 385, 3))  # 121-384 every 3 hours
        logger.info(f"Processing forecast hours 0 to 384")
        
        files_found = 0
        for hour in hours:
            file_name = f"gfswave.t{model_run}z.{model_name}.f{str(hour).zfill(3)}.grib2"
            file_path = Path(settings.data_dir) / file_name
            
            if not file_path.exists():
                logger.debug(f"File not found: {file_name}")
                continue
                
            logger.debug(f"Processing file: {file_name}")
            files_found += 1
            forecast = self.process_grib_file(file_path, lat, lon)
            if forecast:
                forecasts.append(forecast)
        
        logger.info(f"Found {files_found} files, processed {len(forecasts)} forecasts")
        
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

    def normalize_longitude(self, lon: float) -> float:
        """Convert longitude from -180/180 to 0/360 format."""
        return lon % 360 if lon < 0 else lon

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