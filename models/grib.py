import xarray as xr
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Grib2File:
    """Class to handle GRIB2 format wave model data files."""
    
    def __init__(self, file_path: Path):
        """Initialize GRIB2 file reader.
        
        Args:
            file_path: Path to the GRIB2 file
        """
        self.file_path = Path(file_path)
        self.forecast_hour = int(self.file_path.stem.split('.')[-2][1:])  # Extract f000 -> 0
        self.dataset = self._open_dataset()
        
    def _open_dataset(self) -> xr.Dataset:
        """Open the GRIB2 file using xarray."""
        try:
            return xr.open_dataset(
                self.file_path,
                engine='cfgrib',
                backend_kwargs={'indexpath': ''}
            )
        except Exception as e:
            logger.error(f"Error opening {self.file_path}: {str(e)}")
            raise
            
    def get_grid_indices(self, lat: float, lon: float, grid_config: Dict) -> tuple[int, int]:
        """Find the nearest grid indices for given coordinates.
        
        Args:
            lat: Target latitude
            lon: Target longitude
            grid_config: Grid configuration from settings
            
        Returns:
            Tuple of (latitude_index, longitude_index)
        """
        # Normalize longitude if needed
        while lon < grid_config["lon"]["start"]:
            lon += 360
        while lon > grid_config["lon"]["end"]:
            lon -= 360
            
        # Find nearest indices
        lat_idx = abs(self.dataset.latitude - lat).argmin().item()
        lon_idx = abs(self.dataset.longitude - lon).argmin().item()
        
        return lat_idx, lon_idx
        
    def get_value_at_indices(self, var_name: str, lat_idx: int, lon_idx: int) -> Optional[float]:
        """Get variable value at specific grid indices.
        
        Args:
            var_name: Name of the variable to extract
            lat_idx: Latitude index
            lon_idx: Longitude index
            
        Returns:
            Value at the specified indices or None if not found
        """
        try:
            if var_name not in self.dataset.data_vars:
                return None
                
            var = self.dataset[var_name]
            if 'orderedSequenceData' in var.dims:
                value = var.isel(
                    orderedSequenceData=0,
                    latitude=lat_idx,
                    longitude=lon_idx
                ).values
            else:
                value = var.isel(
                    latitude=lat_idx,
                    longitude=lon_idx
                ).values
                
            return float(value)
            
        except Exception as e:
            logger.error(f"Error getting {var_name} at ({lat_idx}, {lon_idx}): {str(e)}")
            return None
            
    def close(self):
        """Close the dataset."""
        try:
            self.dataset.close()
        except Exception as e:
            logger.error(f"Error closing dataset: {str(e)}") 