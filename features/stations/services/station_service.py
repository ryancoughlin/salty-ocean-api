import json
import logging
from typing import Dict, Optional, List
from fastapi import HTTPException
from pathlib import Path

from features.common.models.station_types import Station, Location
from features.waves.models.ndbc_types import NDBCObservation
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient
from core.cache import cached

logger = logging.getLogger(__name__)

def station_observation_key_builder(
    func,
    namespace: str = "",
    *args,
    **kwargs
) -> str:
    """Build cache key for station observations."""
    station_id = kwargs.get("station_id", "")
    return f"{namespace}:{station_id}"

class StationService:
    def __init__(self, stations_file: Path = Path("ndbcStations.json")):
        self.stations_file = stations_file
        self._stations: Optional[List[Station]] = None
        self.buoy_client = NDBCBuoyClient()
        
    def _load_stations(self) -> List[Station]:
        """Load NDBC stations from JSON file."""
        if self._stations is not None:
            return self._stations
            
        try:
            with open(self.stations_file) as f:
                stations_data = json.load(f)
                self._stations = [
                    Station(
                        station_id=station["id"],
                        name=station["name"],
                        location=Location(
                            type="Point",
                            coordinates=list(station["location"]["coordinates"])
                        ),
                        type=station.get("type", "buoy")
                    )
                    for station in stations_data
                ]
                return self._stations
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading station data: {str(e)}"
            )

    def get_station(self, station_id: str) -> Station:
        """Get station by ID."""
        stations = self._load_stations()
        station = next(
            (s for s in stations if s.station_id == station_id),
            None
        )
        
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found"
            )
        return station

    @cached(
        namespace="station_observations",
        expire=900,  # 15 minutes in seconds
        key_builder=station_observation_key_builder
    )
    async def get_station_observations(self, station_id: str) -> NDBCObservation:
        """Get current observations for a station."""
        # Verify station exists
        station = self.get_station(station_id)
        
        # Get observations from NDBC
        observation = await self.buoy_client.get_observation(station_id, {
            "name": station.name,
            "location": {
                "type": "Point",
                "coordinates": station.location.coordinates
            }
        })
        if not observation:
            raise HTTPException(
                status_code=404,
                detail=f"No observations found for station {station_id}"
            )
        
        return observation 