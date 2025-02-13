import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Tuple
import json
import xarray as xr
import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor

from core.config import settings
from utils.model_time import get_latest_model_run
from core.cache import cached

logger = logging.getLogger(__name__)

class WaveDataProcessor:
    _cached_dataset = None
    _cached_model_run = None
    
    def __init__(self, data_dir: str = settings.data_dir):
        self.data_dir = Path(data_dir)
        
    def get_current_model_run(self) -> tuple[str, str]:
        """Get latest available model run."""
        return get_latest_model_run()

    def load_dataset(self, model_run: str, date: str) -> Optional[xr.Dataset]:
        """Load the dataset for the current model run."""
        if self._cached_dataset is not None and self._cached_model_run == model_run:
            return self._cached_dataset
            
        logger.info(f"Loading forecast files for model run {date} {model_run}z")
        start_time = datetime.now()
        
        try:
            # Get list of files
            forecast_files = []
            for hour in settings.forecast_hours:
                filename = f"gfswave.t{model_run}z.{settings.models['atlantic']['name']}.f{str(hour).zfill(3)}.grib2"
                file_path = self.data_dir / filename
                if file_path.exists():
                    forecast_files.append((hour, file_path))
            
            if not forecast_files:
                logger.warning("No forecast files found")
                return None
                
            logger.info(f"Loading {len(forecast_files)} forecast files")
            
            # Process files
            run_time = datetime.strptime(f"{date} {model_run}00", "%Y%m%d %H%M")
            run_time = run_time.replace(tzinfo=timezone.utc)
            
            all_datasets = []
            for hour, file_path in forecast_files:
                try:
                    ds = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={
                        'time_dims': ('time',),
                        'indexpath': '',
                        'filter_by_keys': {'typeOfLevel': 'surface'}
                    })
                    forecast_time = run_time + timedelta(hours=hour)
                    ds = ds.assign_coords(time=forecast_time)
                    all_datasets.append(ds)
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {str(e)}")
                    continue
            
            if not all_datasets:
                logger.warning("No forecast data could be loaded")
                return None
            
            try:
                combined = xr.concat(all_datasets, dim="time", combine_attrs="override")
                combined = combined.sortby('time')
                
                logger.info(f"Processed {len(all_datasets)} forecasts in {(datetime.now() - start_time).total_seconds():.1f}s")
                logger.info(f"Time range: {combined.time.values[0]} to {combined.time.values[-1]}")
                
                self._cached_dataset = combined
                self._cached_model_run = model_run
                return combined
                
            finally:
                for ds in all_datasets:
                    ds.close()
                    
        except Exception as e:
            logger.error(f"Error loading forecast dataset: {str(e)}")
            return None

    def process_station_forecast(self, station_id: str) -> Dict:
        """Process wave model forecast for a station."""
        try:
            # Get station metadata
            station = self._get_station_metadata(station_id)
            if not station:
                raise ValueError(f"Station {station_id} not found")
            
            # Get current model run info
            model_run, date = self.get_current_model_run()
            
            # Load dataset
            full_forecast = self.load_dataset(model_run, date)
            if full_forecast is None:
                logger.warning(f"No forecast data available for station {station_id}")
                return {
                    "station_id": station_id,
                    "name": station["name"],
                    "location": station["location"],
                    "model_run": f"{date} {model_run}z",
                    "forecasts": [],
                    "metadata": station,
                    "status": "no_data"
                }

            # Find nearest grid point (convert longitude to 0-360)
            lat = station["location"]["coordinates"][1]
            lon = station["location"]["coordinates"][0]
            if lon < 0:
                lon = lon + 360
            
            lat_idx = abs(full_forecast.latitude - lat).argmin().item()
            lon_idx = abs(full_forecast.longitude - lon).argmin().item()
            
            # Known variable mapping with unit conversions
            variables = {
                'ws': ('wind_speed', lambda x: x * 2.237),        # m/s to mph
                'wdir': ('wind_direction', lambda x: x),          # degrees
                'swh': ('wave_height', lambda x: x * 3.28084),    # m to ft
                'perpw': ('wave_period', lambda x: x),            # seconds
                'dirpw': ('wave_direction', lambda x: x),         # degrees
                'shww': ('wind_wave_height', lambda x: x * 3.28084),  # m to ft
                'mpww': ('wind_wave_period', lambda x: x),        # seconds
                'wvdir': ('wind_wave_direction', lambda x: x),    # degrees
                'shts': ('swell_height', lambda x: x * 3.28084),  # m to ft
                'mpts': ('swell_period', lambda x: x),            # seconds
                'swdir': ('swell_direction', lambda x: x)         # degrees
            }
            
            # Extract point data for all variables
            point_data = {}
            for var, (output_name, convert) in variables.items():
                if var in full_forecast:
                    data = full_forecast[var].isel(latitude=lat_idx, longitude=lon_idx).values
                    point_data[output_name] = convert(data)
            
            # Process each timestamp
            forecasts = []
            for i, time in enumerate(full_forecast.time.values):
                utc_time = pd.Timestamp(time).tz_localize('UTC')
                forecast_time = utc_time.tz_convert('EST')
                forecast = {"time": forecast_time.isoformat()}
                
                # Add wind data
                wind = {}
                if 'wind_speed' in point_data and 'wind_direction' in point_data:
                    speed = float(point_data['wind_speed'][i])
                    direction = float(point_data['wind_direction'][i])
                    if not pd.isna(speed) and not pd.isna(direction):
                        wind = {
                            'speed': round(speed, 1),
                            'direction': round(direction, 1)
                        }
                
                # Add wave data
                wave = {}
                wave_vars = ['wave_height', 'wave_period', 'wave_direction', 
                           'wind_wave_height', 'wind_wave_period', 'wind_wave_direction']
                for var in wave_vars:
                    if var in point_data:
                        val = float(point_data[var][i])
                        if not pd.isna(val):
                            wave[var.replace('wave_', '')] = round(val, 1)
                
                # Add swell data
                swell = []
                if all(var in point_data for var in ['swell_height', 'swell_period', 'swell_direction']):
                    for j in range(3):  # 3 swell components
                        height = float(point_data['swell_height'][i, j])
                        period = float(point_data['swell_period'][i, j])
                        direction = float(point_data['swell_direction'][i, j])
                        
                        if not any(pd.isna(x) for x in [height, period, direction]):
                            swell.append({
                                'height': round(height, 1),
                                'period': round(period, 1),
                                'direction': round(direction, 1)
                            })

                forecast.update({
                    'wind': wind,
                    'wave': wave,
                    'swell': swell
                })
                
                forecasts.append(forecast)
            
            return {
                "station_id": station_id,
                "name": station["name"],
                "location": station["location"],
                "model_run": f"{date} {model_run}z",
                "forecasts": forecasts,
                "metadata": station
            }
            
        except Exception as e:
            logger.error(f"Error processing forecast for station {station_id}: {str(e)}")
            raise
            
    def _get_station_metadata(self, station_id: str) -> Optional[Dict]:
        """Get station metadata from JSON file."""
        try:
            with open("ndbcStations.json") as f:
                stations = json.load(f)
                return next((s for s in stations if s["id"] == station_id), None)
        except Exception as e:
            logger.error(f"Error loading station metadata: {str(e)}")
            raise 