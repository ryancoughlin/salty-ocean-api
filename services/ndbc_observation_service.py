import aiohttp
from datetime import datetime, timezone
import logging
from typing import Dict, Any, List, Optional
from core.config import settings
from models.buoy import WindData, WaveData, DataAge, NDBCObservation

logger = logging.getLogger(__name__)

class NDBCObservationService:
    """Service for fetching and parsing NDBC buoy data."""
    
    def __init__(self):
        self.base_url = settings.ndbc_base_url
        
    async def get_realtime_observations(self, station_id: str) -> Dict[str, Any]:
        """Fetch and parse real-time observations from NDBC."""
        try:
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
            
            # Create observation model
            observation = NDBCObservation(
                time=timestamp,
                wind=wind,
                wave=wave,
                data_age=data_age
            )
            
            # Convert to dict and adjust timestamp key
            result = observation.model_dump()
            result['timestamp'] = result.pop('time')
                    
            return result
        except Exception as e:
            logger.error(f"Error fetching observations for station {station_id}: {str(e)}")
            raise
        
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
            direction = float(data[5]) if len(data) > 5 and data[5] != "MM" else None
            speed = float(data[6]) if len(data) > 6 and data[6] != "MM" else None
            return WindData(direction=direction, speed=speed)
        except (ValueError, IndexError):
            return WindData()
            
    def _parse_wave_data(self, data: List[str]) -> WaveData:
        """Parse NDBC wave fields into WaveData model."""
        try:
            height = float(data[8]) if len(data) > 8 and data[8] != "MM" else None
            period = float(data[9]) if len(data) > 9 and data[9] != "MM" else None
            direction = float(data[11]) if len(data) > 11 and data[11] != "MM" else None
            return WaveData(
                height=height,
                period=period,
                direction=direction
            )
        except (ValueError, IndexError):
            return WaveData()