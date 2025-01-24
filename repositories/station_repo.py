from pathlib import Path
import json
from typing import Dict, List, Optional, Tuple

class StationRepository:
    def __init__(self, stations_file: Path):
        self.stations_file = stations_file
        self._stations = None

    def load_stations(self) -> List[Dict]:
        if not self._stations:
            with open(self.stations_file) as f:
                self._stations = json.load(f)
        return self._stations

    def get_station(self, station_id: str) -> Optional[Dict]:
        stations = self.load_stations()
        return next((s for s in stations if s["id"] == station_id), None)
        
    def get_station_coordinates(self, station_id: str) -> Optional[Tuple[float, float]]:
        """Get the coordinates (lon, lat) for a station.
        
        Args:
            station_id: Station identifier
            
        Returns:
            Tuple of (longitude, latitude) if station found, None otherwise
        """
        station = self.get_station(station_id)
        if station and "location" in station:
            # NDBC format is [lon, lat]
            return tuple(station["location"]["coordinates"])
        return None 