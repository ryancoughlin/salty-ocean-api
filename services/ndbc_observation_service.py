import aiohttp
from datetime import datetime, timezone
import logging
from typing import Dict, Any, List
from core.config import settings
from models.buoy import WindData, WaveData, DataAge, NDBCObservation

logger = logging.getLogger(__name__)

class NDBCObservationService:
    """Service for fetching and parsing NDBC buoy data."""
    
    def __init__(self):
        self.base_url = settings.ndbc_base_url
        
    async def get_realtime_observations(self, station_id: str) -> Dict[str, Any]:
        """Fetch and parse real-time observations from NDBC.
        
        Args:
            station_id: The NDBC station identifier (e.g. "44098")
            
        Returns:
            Dict containing:
                - timestamp: UTC datetime of observation
                - wind: WindData with speed and direction
                - wave: WaveData with height, period, and direction
                - data_age: DataAge with minutes and isStale
        """
        # Fetch raw data
        url = f"{self.base_url}/{station_id}.txt"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                text = await response.text()

        # Parse first data line (skip headers)
        data = None
        for line in text.strip().split('\n'):
            if not line.startswith('#'):
                data = line.split()
                break
                
        if not data or len(data) < 5:
            raise ValueError("Invalid or missing data from NDBC")
            
        # Parse timestamp and calculate age
        timestamp = self._parse_timestamp(data[:5])
        age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60
            
        # Parse wind and wave data
        wind = self._parse_wind_data(data)
        wave = self._parse_wave_data(data)
        
        # Create data age model
        data_age = DataAge(
            minutes=round(age_minutes, 1),
            isStale=age_minutes > 45
        )
        
        # Create and return observation
        observation = NDBCObservation(
            time=timestamp,
            wind=wind,
            wave=wave,
            data_age=data_age
        )
                
        return observation.model_dump()
        
    def _parse_timestamp(self, time_data: List[str]) -> datetime:
        """Parse NDBC timestamp fields into datetime."""
        try:
            return datetime(
                year=int(time_data[0]),
                month=int(time_data[1]),
                day=int(time_data[2]),
                hour=int(time_data[3]) if time_data[3] != "MM" else 0,
                minute=int(time_data[4]) if time_data[4] != "MM" else 0,
                tzinfo=timezone.utc
            )
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid timestamp data: {e}")
            
    def _parse_wind_data(self, data: List[str]) -> WindData:
        """Parse NDBC wind fields into WindData model."""
        try:
            return WindData(
                direction=float(data[5]) if len(data) > 5 and data[5] != "MM" else None,
                speed=float(data[6]) if len(data) > 6 and data[6] != "MM" else None
            )
        except (ValueError, IndexError):
            return WindData()  # Return empty model if parsing fails
            
    def _parse_wave_data(self, data: List[str]) -> WaveData:
        """Parse NDBC wave fields into WaveData model."""
        try:
            return WaveData(
                height=float(data[8]) if len(data) > 8 and data[8] != "MM" else None,
                period=float(data[9]) if len(data) > 9 and data[9] != "MM" else None,
                direction=float(data[11]) if len(data) > 11 and data[11] != "MM" else None
            )
        except (ValueError, IndexError):
            return WaveData()  # Return empty model if parsing fails