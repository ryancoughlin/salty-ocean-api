import xarray as xr
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)

class Grib2File:
    """Class to handle GRIB2 format wave model data files."""
    
    _dataset_cache = {}  # Class-level cache for datasets
    _indices_cache = {}  # Class-level cache for grid indices
    
    def __init__(self, file_path: Path):
        """Initialize GRIB2 file reader.
        
        Args:
            file_path: Path to the GRIB2 file
        """
        start_time = time.time()
        self.file_path = Path(file_path)
        
        # Extract forecast hour from filename (e.g., gfswave.t06z.atlocn.0p16.f000.grib2)
        parts = self.file_path.stem.split('.')
        for part in parts:
            if part.startswith('f') and part[1:].isdigit():
                self.forecast_hour = int(part[1:])
                break
        else:
            logger.error(f"Could not find forecast hour in filename: {self.file_path.name}")
            raise ValueError(f"Invalid filename format: {self.file_path.name}")
            
        logger.debug(f"Initialized GRIB2 file: {self.file_path.name}, forecast hour: {self.forecast_hour}")
        self.dataset = self._get_dataset()
        logger.debug(f"GRIB2 file initialization took {time.time() - start_time:.3f}s")
        
    def _get_dataset(self) -> xr.Dataset:
        """Get dataset from cache or open new one."""
        start_time = time.time()
        if str(self.file_path) not in self._dataset_cache:
            try:
                logger.debug(f"Opening new dataset: {self.file_path.name}")
                t0 = time.time()
                self._dataset_cache[str(self.file_path)] = xr.open_dataset(
                    self.file_path,
                    engine='cfgrib',
                    backend_kwargs={'indexpath': ''}
                )
                logger.debug(f"Opened dataset in {time.time() - t0:.3f}s")
            except Exception as e:
                logger.error(f"Error opening {self.file_path}: {str(e)}")
                raise
        else:
            logger.debug(f"Using cached dataset: {self.file_path.name}")
            
        logger.debug(f"Dataset retrieval took {time.time() - start_time:.3f}s")
        return self._dataset_cache[str(self.file_path)]
            
    def get_grid_indices(self, lat: float, lon: float, grid_config: Dict) -> tuple[int, int]:
        """Find the nearest grid indices for given coordinates.
        
        Args:
            lat: Target latitude
            lon: Target longitude
            grid_config: Grid configuration from settings
            
        Returns:
            Tuple of (latitude_index, longitude_index)
        """
        # Check cache first
        cache_key = f"{lat}_{lon}_{grid_config['lon']['start']}_{grid_config['lon']['end']}"
        if cache_key in self._indices_cache:
            logger.debug(f"Using cached grid indices for {cache_key}")
            return self._indices_cache[cache_key]
            
        start_time = time.time()
        logger.debug(f"Finding grid indices for lat={lat}, lon={lon}")
        logger.debug(f"Grid config: {grid_config}")
        
        # Normalize longitude if needed
        original_lon = lon
        while lon < grid_config["lon"]["start"]:
            lon += 360
        while lon > grid_config["lon"]["end"]:
            lon -= 360
        if original_lon != lon:
            logger.debug(f"Normalized longitude from {original_lon} to {lon}")
            
        # Find nearest indices
        t0 = time.time()
        lat_idx = abs(self.dataset.latitude - lat).argmin().item()
        lon_idx = abs(self.dataset.longitude - lon).argmin().item()
        logger.debug(f"Found indices in {time.time() - t0:.3f}s")
        
        # Cache the result
        self._indices_cache[cache_key] = (lat_idx, lon_idx)
        
        logger.debug(f"Grid point: lat={float(self.dataset.latitude[lat_idx].item())}, lon={float(self.dataset.longitude[lon_idx].item())}")
        logger.debug(f"Grid index computation took {time.time() - start_time:.3f}s")
        
        return lat_idx, lon_idx
        
    def get_value_at_indices(self, variable: str, lat_idx: int, lon_idx: int) -> Optional[float]:
        """Get value at specified indices for a variable, handling missing values."""
        try:
            value = self.dataset[variable].values[0, lat_idx, lon_idx]
            if value == 3.4028234663852886e+38:  # GRIB missing value
                return None
            return value
        except (KeyError, IndexError):
            return None
            
    @classmethod
    def clear_cache(cls):
        """Clear all caches."""
        logger.debug(f"Clearing caches ({len(cls._dataset_cache)} datasets, {len(cls._indices_cache)} indices)")
        for dataset in cls._dataset_cache.values():
            dataset.close()
        cls._dataset_cache.clear()
        cls._indices_cache.clear()
            
    def close(self):
        """Close the dataset."""
        # Don't actually close since we're caching
        pass 