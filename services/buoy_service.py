import aiohttp
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional
from models.buoy import WindData, WaveData, DataAge, NDBCObservation
from core.config import settings

logger = logging.getLogger(__name__)

class BuoyService:
    """Service for fetching and processing NDBC buoy data."""
    
    def __init__(self, base_url: str = settings.ndbc_base_url):
        self.base_url = base_url
        
    async def get_observation(self, station_id: str) -> NDBCObservation:
        """Fetch and parse real-time observations for a station.
        
        Args:
            station_id: NDBC station identifier (e.g. "44098")
            
        Returns:
            NDBCObservation with current conditions
            
        Raises:
            ValueError: If station data is invalid or missing
            HTTPError: If NDBC service is unavailable
        """
        raw_data = await self._fetch_raw_data(station_id)
        return self._parse_observation(raw_data)
    
    async def _fetch_raw_data(self, station_id: str) -> str:
        """Fetch raw data from NDBC station."""
        url = f"{self.base_url}/{station_id}.txt"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
    
    def _parse_observation(self, raw_data: str) -> NDBCObservation:
        """Parse raw NDBC data into observation model."""
        # Get first non-header line
        data = None
        for line in raw_data.strip().split('\n'):
            if not line.startswith('#'):
                data = line.split()
                break
        
        if not data or len(data) < 5:
            raise ValueError("Invalid or missing data from NDBC")
        
        # Parse components
        timestamp = self._parse_timestamp(data[:5])
        wind = self._parse_wind_data(data)
        wave = self._parse_wave_data(data)
        data_age = self._calculate_data_age(timestamp)
        
        return NDBCObservation(
            time=timestamp,
            wind=wind,
            wave=wave,
            data_age=data_age
        )
    
    def _parse_timestamp(self, time_data: list[str]) -> datetime:
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
    
    def _parse_wind_data(self, data: list[str]) -> WindData:
        """Parse NDBC wind fields into WindData model."""
        try:
            return WindData(
                direction=float(data[5]) if len(data) > 5 and data[5] != "MM" else None,
                speed=float(data[6]) if len(data) > 6 and data[6] != "MM" else None
            )
        except (ValueError, IndexError):
            return WindData()
    
    def _parse_wave_data(self, data: list[str]) -> WaveData:
        """Parse NDBC wave fields into WaveData model."""
        try:
            return WaveData(
                height=float(data[8]) if len(data) > 8 and data[8] != "MM" else None,
                period=float(data[9]) if len(data) > 9 and data[9] != "MM" else None,
                direction=float(data[11]) if len(data) > 11 and data[11] != "MM" else None
            )
        except (ValueError, IndexError):
            return WaveData()
    
    def _calculate_data_age(self, timestamp: datetime) -> DataAge:
        """Calculate age of data from timestamp."""
        age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60
        return DataAge(
            minutes=round(age_minutes, 1),
            isStale=age_minutes > 45
        ) 