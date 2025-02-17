import json
import logging
from typing import Dict, Optional
from fastapi import HTTPException
from pathlib import Path

logger = logging.getLogger(__name__)

class StationService:
    def __init__(self, stations_file: Path = Path("ndbcStations.json")):
        self.stations_file = stations_file
        self._stations: Optional[Dict] = None
        
    def _load_stations(self) -> Dict:
        """Load NDBC stations from JSON file."""
        if self._stations is not None:
            return self._stations
            
        try:
            with open(self.stations_file) as f:
                self._stations = json.load(f)
                return self._stations
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading station data: {str(e)}"
            )

    def get_station(self, station_id: str) -> Dict:
        """Get station by ID."""
        stations = self._load_stations()
        station = next(
            (s for s in stations if s["id"] == station_id),
            None
        )
        
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found"
            )
        return station 