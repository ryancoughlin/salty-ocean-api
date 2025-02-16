import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Tuple, NamedTuple
import json
import xarray as xr
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from core.config import settings
from utils.model_time import get_latest_model_run
from core.cache import cached

logger = logging.getLogger(__name__)

class StationIndices(NamedTuple):
    """Store pre-computed station indices."""
    lat_idx: int
    lon_idx: int

class WaveDataProcessor:
    _cached_dataset = None
    _cached_model_run = None
    _cached_date = None
    _station_indices: Dict[str, StationIndices] = {}
    _stations_metadata: Dict[str, Dict] = {}
    
    def __init__(self, data_dir: str = settings.data_dir):
        self.data_dir = Path(data_dir)
        self._load_station_metadata()
        
    def _load_station_metadata(self):
        """Load station metadata and pre-compute indices."""
        try:
            with open("ndbcStations.json") as f:
                stations = json.load(f)
                self._stations_metadata = {s["id"]: s for s in stations}
        except Exception as e:
            logger.error(f"Error loading station metadata: {str(e)}")
            raise

    def _compute_station_indices(self, dataset: xr.Dataset, station_id: str) -> Optional[StationIndices]:
        """Compute and cache station indices. Returns None if station is outside model grid."""
        if station_id in self._station_indices:
            return self._station_indices[station_id]
            
        station = self._stations_metadata.get(station_id)
        if not station:
            raise ValueError(f"Station {station_id} not found")
            
        # Get coordinates
        lat = station["location"]["coordinates"][1]
        lon = station["location"]["coordinates"][0]
        if lon < 0:
            lon = lon + 360
            
        # Check if station is within model grid bounds
        if (lon < dataset.longitude.min().item() or 
            lon > dataset.longitude.max().item() or
            lat < dataset.latitude.min().item() or
            lat > dataset.latitude.max().item()):
            return None
            
        try:
            # Find nearest points
            lat_idx = abs(dataset.latitude - lat).argmin().item()
            lon_idx = abs(dataset.longitude - lon).argmin().item()
            
            # Cache indices
            indices = StationIndices(lat_idx=lat_idx, lon_idx=lon_idx)
            self._station_indices[station_id] = indices
            return indices
        except Exception as e:
            logger.error(f"Error computing indices for station {station_id}: {str(e)}")
            return None

    def get_current_model_run(self) -> tuple[str, str]:
        """Get latest available model run."""
        return get_latest_model_run()

    def _should_reload_dataset(self, model_run: str, date: str) -> bool:
        """Check if dataset needs to be reloaded."""
        return (
            self._cached_dataset is None or 
            self._cached_model_run != model_run or
            self._cached_date != date
        )

    def get_dataset(self) -> Optional[xr.Dataset]:
        """Get the current cached dataset."""
        model_run, date = self.get_current_model_run()
        
        if self._should_reload_dataset(model_run, date):
            return self.load_dataset(model_run, date)
            
        return self._cached_dataset

    def load_dataset(self, model_run: str, date: str) -> Optional[xr.Dataset]:
        """Load the dataset for the current model run."""
        if not self._should_reload_dataset(model_run, date):
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
                
            # Process files
            run_time = datetime.strptime(f"{date} {model_run}00", "%Y%m%d %H%M")
            run_time = run_time.replace(tzinfo=timezone.utc)
            
            # Use ThreadPoolExecutor for parallel file loading
            with ThreadPoolExecutor() as executor:
                futures = []
                for hour, file_path in forecast_files:
                    future = executor.submit(
                        self._load_grib_file,
                        file_path=file_path,
                        forecast_time=run_time + timedelta(hours=hour)
                    )
                    futures.append(future)
                
                # Gather results
                all_datasets = []
                for future in futures:
                    try:
                        ds = future.result()
                        if ds is not None:
                            all_datasets.append(ds)
                    except Exception as e:
                        logger.error(f"Error loading forecast file: {str(e)}")
            
            if not all_datasets:
                logger.warning("No forecast data could be loaded")
                return None
            
            try:
                combined = xr.concat(all_datasets, dim="time", combine_attrs="override")
                combined = combined.sortby('time')
                
                logger.info(f"Processed {len(all_datasets)} forecasts in {(datetime.now() - start_time).total_seconds():.1f}s")
                
                # Clear station indices cache when dataset changes
                self._station_indices.clear()
                
                # Update cache
                self._cached_dataset = combined
                self._cached_model_run = model_run
                self._cached_date = date
                return combined
                
            finally:
                for ds in all_datasets:
                    ds.close()
                    
        except Exception as e:
            logger.error(f"Error loading forecast dataset: {str(e)}")
            return None
            
    def _load_grib_file(self, file_path: Path, forecast_time: datetime) -> Optional[xr.Dataset]:
        """Load a single GRIB2 file."""
        try:
            ds = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={
                'time_dims': ('time',),
                'indexpath': '',
                'filter_by_keys': {'typeOfLevel': 'surface'}
            })
            return ds.assign_coords(time=forecast_time)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {str(e)}")
            return None

    def process_station_forecast(self, station_id: str) -> Dict:
        """Process wave model forecast for a station."""
        try:
            # Get station metadata from pre-loaded cache
            station = self._stations_metadata.get(station_id)
            if not station:
                raise ValueError(f"Station {station_id} not found")
            
            # Get current model run info and dataset
            model_run, date = self.get_current_model_run()
            full_forecast = self.get_dataset()
            
            if full_forecast is None:
                return self._build_empty_response(station_id, station, date, model_run, "no_data")

            # Get cached indices or compute new ones
            indices = self._compute_station_indices(full_forecast, station_id)
            if indices is None:
                return self._build_empty_response(station_id, station, date, model_run, "outside_grid")

            # Extract all variables at once using cached indices
            point_data = {
                # Wind variables (m/s to mph)
                'wind_speed': full_forecast['ws'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values * 2.237,
                'wind_direction': full_forecast['wdir'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values,
                
                # Wave variables (m to ft)
                'wave_height': full_forecast['swh'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values * 3.28084,
                'wave_period': full_forecast['perpw'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values,
                'wave_direction': full_forecast['dirpw'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values,
                
                # Wind wave variables (m to ft)
                'wind_wave_height': full_forecast['shww'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values * 3.28084,
                'wind_wave_period': full_forecast['mpww'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values,
                'wind_wave_direction': full_forecast['wvdir'].isel(latitude=indices.lat_idx, longitude=indices.lon_idx).values,
            }
            
            # Process each timestamp
            forecasts = []
            for i, time in enumerate(full_forecast.time.values):
                utc_time = pd.Timestamp(time).tz_localize('UTC')
                forecast_time = utc_time.tz_convert('EST')
                
                # Helper function to handle invalid values
                def format_value(value, value_type=None):
                    try:
                        val = float(value)
                        if pd.isna(val) or np.isnan(val) or np.isinf(val):
                            return None
                            
                        # Apply specific rounding rules
                        if value_type == 'wave_height':
                            return round(val, 1)  # Wave height to 1 decimal
                        elif value_type == 'period':
                            return round(val)  # Wave period to whole number
                        elif value_type in ['direction', 'speed']:
                            return round(val)  # Wind values to whole numbers
                        
                        return val
                    except (TypeError, ValueError):
                        return None
                
                # Build forecast object with exact same structure as example
                forecast = {
                    'time': forecast_time.isoformat(),
                    'wind': {
                        'speed': format_value(point_data['wind_speed'][i], 'speed'),
                        'direction': format_value(point_data['wind_direction'][i], 'direction')
                    },
                    'wave': {
                        'height': format_value(point_data['wave_height'][i], 'wave_height'),
                        'period': format_value(point_data['wave_period'][i], 'period'),
                        'direction': format_value(point_data['wave_direction'][i], 'direction'),
                        'wind_height': format_value(point_data['wind_wave_height'][i], 'wave_height'),
                        'wind_period': format_value(point_data['wind_wave_period'][i], 'period'),
                        'wind_direction': format_value(point_data['wind_wave_direction'][i], 'direction')
                    }
                }
                
                forecasts.append(forecast)
            
            return {
                "station_id": station_id,
                "name": station["name"],
                "location": station["location"],
                "model_run": f"{date} {model_run}z",
                "forecasts": forecasts,
                "metadata": station,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error processing forecast for station {station_id}: {str(e)}")
            return self._build_empty_response(station_id, station, date, model_run, "error")

    def _build_empty_response(self, station_id: str, station: Dict, date: str, model_run: str, status: str) -> Dict:
        """Build an empty response for a station when data is not available."""
        return {
            "station_id": station_id,
            "name": station["name"],
            "location": station["location"],
            "model_run": f"{date} {model_run}z",
            "forecasts": [],
            "metadata": station,
            "status": status
        }

    async def preload_dataset(self) -> Optional[xr.Dataset]:
        """Preload dataset into cache."""
        model_run, date = self.get_current_model_run()
        
        try:
            dataset = self.load_dataset(model_run, date)
            if dataset is not None:
                return dataset
            return None
        except Exception as e:
            logger.error(f"Error preloading dataset: {str(e)}")
            return None 