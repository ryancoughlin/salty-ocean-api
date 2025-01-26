import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import json
import xarray as xr
import pandas as pd
import asyncio

from core.config import settings
from utils.model_time import get_latest_model_run

logger = logging.getLogger(__name__)

class WaveDataProcessor:
    # Static cache shared across all instances
    _cached_dataset = None
    _cached_model_run = None
    
    def __init__(self, data_dir: str = settings.data_dir):
        self.data_dir = Path(data_dir)
        
    def get_current_model_run(self) -> tuple[str, str]:
        """Get latest available model run."""
        return get_latest_model_run()

    async def preload_dataset(self) -> None:
        """Preload the dataset for the current model run."""
        try:
            model_run, date = self.get_current_model_run()
            logger.info(f"Preloading dataset for model run {date} {model_run}z")
            start_time = datetime.now()
            
            # Load dataset in executor to not block event loop
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._load_forecast_dataset,
                model_run,
                date
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Completed dataset preload in {duration:.2f}s")
        except Exception as e:
            logger.error(f"Error preloading dataset: {str(e)}")
            raise

    def _load_forecast_dataset(self, model_run: str, date: str) -> xr.Dataset:
        """Load and combine all forecast files for a model run."""
        if self._cached_dataset is not None and self._cached_model_run == model_run:
            logger.info("Using cached dataset")
            return self._cached_dataset
            
        logger.info("Loading forecast files...")
        start_time = datetime.now()
        
        # Get list of all forecast files
        forecast_files = []
        for hour in sorted(settings.forecast_hours):  # Sort to ensure chronological order
            filename = f"gfswave.t{model_run}z.{settings.models['atlantic']['name']}.f{str(hour).zfill(3)}.grib2"
            file_path = self.data_dir / filename
            if file_path.exists():
                forecast_files.append((hour, file_path))
        
        if not forecast_files:
            raise ValueError("No forecast files found")
        
        # Load datasets and ensure time dimension is preserved
        datasets = []
        model_run_time = datetime.strptime(f"{date} {model_run}00", "%Y%m%d %H%M")
        model_run_time = model_run_time.replace(tzinfo=timezone.utc)
        
        for hour, file_path in forecast_files:
            ds = xr.open_dataset(file_path, engine='cfgrib')
            
            # Calculate the actual forecast time for this file
            forecast_time = model_run_time + timedelta(hours=hour)
            
            # Ensure the dataset has the correct time coordinate
            ds = ds.assign_coords(time=forecast_time)
            
            # Log time values for debugging
            logger.debug(f"Processing forecast hour {hour}, time: {forecast_time}")
            
            datasets.append(ds)
        
        if not datasets:
            raise ValueError("No datasets could be loaded")
        
        # Combine all datasets along time dimension
        WaveDataProcessor._cached_dataset = xr.concat(datasets, dim="time", combine_attrs="override")
        WaveDataProcessor._cached_model_run = model_run
        
        # Verify time dimension is monotonically increasing
        times = WaveDataProcessor._cached_dataset.time.values
        if not all(times[i] < times[i+1] for i in range(len(times)-1)):
            logger.error("Time dimension is not monotonically increasing")
            logger.error(f"Time values: {times}")
            raise ValueError("Invalid time dimension in combined dataset")
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Loaded and combined {len(forecast_files)} forecast files in {duration:.2f}s")
        logger.info(f"Time range: {times[0]} to {times[-1]}")
        
        return WaveDataProcessor._cached_dataset

    def process_station_forecast(self, station_id: str) -> Dict:
        """Process wave model forecast for a station."""
        try:
            # Get station metadata
            station = self._get_station_metadata(station_id)
            if not station:
                raise ValueError(f"Station {station_id} not found")
            
            # Get current model run info
            model_run, date = self.get_current_model_run()
            
            # Load or get cached dataset
            full_forecast = self._load_forecast_dataset(model_run, date)
            logger.info(f"Processing {len(full_forecast.time)} forecasts")
            
            # Find nearest grid point (convert longitude to 0-360)
            lat = station["location"]["coordinates"][1]
            lon = station["location"]["coordinates"][0]
            if lon < 0:
                lon = lon + 360
            
            lat_idx = abs(full_forecast.latitude - lat).argmin().item()
            lon_idx = abs(full_forecast.longitude - lon).argmin().item()
            
            # Simple 1:1 variable mapping with unit conversions
            variables = {
                # Wind (m/s to mph)
                'ws': ('wind_speed', lambda x: x * 2.237),
                'wdir': ('wind_direction', lambda x: x),  # degrees, no conversion
                # Wave heights (m to ft)
                'swh': ('wave_height', lambda x: x * 3.28084),
                'shww': ('wind_wave_height', lambda x: x * 3.28084),
                'shts': ('swell_height', lambda x: x * 3.28084),
                # Periods (seconds, no conversion needed)
                'perpw': ('wave_period', lambda x: x),
                'mpww': ('wind_wave_period', lambda x: x),
                'mpts': ('swell_period', lambda x: x),
                # Directions (degrees, no conversion needed)
                'dirpw': ('wave_direction', lambda x: x),
                'wvdir': ('wind_wave_direction', lambda x: x),
                'swdir': ('swell_direction', lambda x: x)
            }
            
            # Extract point data for all variables
            point_data = {}
            for var, (output_name, convert) in variables.items():
                if var in full_forecast:
                    # Extract and convert units
                    data = full_forecast[var].isel(
                        latitude=lat_idx, 
                        longitude=lon_idx
                    ).values
                    point_data[output_name] = convert(data)
            
            # Process each timestamp
            forecasts = []
            for i, time in enumerate(full_forecast.time.values):
                forecast = {"time": pd.Timestamp(time).isoformat()}
                
                # Group variables by type
                wind = {}
                wave = {}
                
                # Add wind data
                if 'wind_speed' in point_data and 'wind_direction' in point_data:
                    speed = float(point_data['wind_speed'][i])
                    direction = float(point_data['wind_direction'][i])
                    if not pd.isna(speed) and not pd.isna(direction):
                        wind = {
                            'speed': round(speed, 1),
                            'direction': round(direction, 1)
                        }
                
                # Add wave data (combined sea and swell)
                wave_vars = {
                    'wave_height': 'height',
                    'wave_period': 'period',
                    'wave_direction': 'direction',
                    'wind_wave_height': 'wind_height',
                    'wind_wave_period': 'wind_period',
                    'wind_wave_direction': 'wind_direction'
                }
                
                for src, dest in wave_vars.items():
                    if src in point_data:
                        val = float(point_data[src][i])
                        if not pd.isna(val):
                            wave[dest] = round(val, 1)
                
                # Add swell components
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
                
                # Add all groups to forecast
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