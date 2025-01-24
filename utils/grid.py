import math
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class GridUtils:
    @staticmethod
    def normalize_longitude(lon: float) -> float:
        """Convert longitude to model grid range."""
        return lon % 360 if lon < 0 else lon

    @staticmethod
    def to_radians(degrees: float) -> float:
        """Convert degrees to radians."""
        return degrees * math.pi / 180

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points.
        
        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point
            
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in km
        d_lat = GridUtils.to_radians(lat2 - lat1)
        d_lon = GridUtils.to_radians(lon2 - lon1)
        
        a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
             math.cos(GridUtils.to_radians(lat1)) *
             math.cos(GridUtils.to_radians(lat2)) *
             math.sin(d_lon / 2) * math.sin(d_lon / 2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def find_nearest_grid_point(lat: float, lon: float, grid_config: Dict) -> Dict:
        """Find the nearest grid point in a model grid for given lat/lon coordinates."""
        # Normalize longitude to model grid range
        while lon < grid_config['lon']['start']:
            lon += 360
        while lon > grid_config['lon']['end']:
            lon -= 360
            
        # Find nearest latitude index
        lat_idx = round((lat - grid_config['lat']['start']) / grid_config['lat']['resolution'])
        lat_idx = max(0, min(lat_idx, grid_config['lat']['size'] - 1))
        
        # Find nearest longitude index
        lon_idx = round((lon - grid_config['lon']['start']) / grid_config['lon']['resolution'])
        lon_idx = max(0, min(lon_idx, grid_config['lon']['size'] - 1))
        
        # Calculate actual coordinates of the grid point
        nearest_lat = grid_config['lat']['start'] + lat_idx * grid_config['lat']['resolution']
        nearest_lon = grid_config['lon']['start'] + lon_idx * grid_config['lon']['resolution']
        
        return {
            'coordinates': {
                'lat': nearest_lat,
                'lon': nearest_lon
            },
            'indices': {
                'lat': lat_idx,
                'lon': lon_idx
            }
        } 