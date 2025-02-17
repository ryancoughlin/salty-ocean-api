import aiohttp
from datetime import datetime, timezone
import logging
from typing import Dict, Any, List, Optional
from models.ndbc_types import NDBCWindData, NDBCWaveData, NDBCMetData, NDBCDataAge, NDBCObservation
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

    def _safe_float(self, value: str) -> Optional[float]:
        """Safely convert NDBC string value to float, handling 'MM' missing data."""
        try:
            return float(value) if value != "MM" else None
        except (ValueError, TypeError):
            return None
    
    def _parse_observation(self, raw_data: str) -> NDBCObservation:
        """Parse raw NDBC data into observation model."""
        # Get first non-header line
        data = None
        header = []
        
        for line in raw_data.strip().split('\n'):
            if line.startswith('#YY'):
                header = line.strip('#').split()
            elif not line.startswith('#'):
                data = line.split()
                break
        
        if not data or len(data) < 5:
            raise ValueError("Invalid or missing data from NDBC")
        
        # Parse components
        timestamp = self._parse_timestamp(data[:5])
        wind = self._parse_wind_data(data)
        wave = self._parse_wave_data(data)
        met = self._parse_met_data(data)
        data_age = self._calculate_data_age(timestamp)
        
        return NDBCObservation(
            time=timestamp,
            wind=wind,
            wave=wave,
            met=met,
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
    
    def _parse_wind_data(self, data: list[str]) -> NDBCWindData:
        """Parse NDBC wind fields into WindData model.
        
        Field positions:
        5: WDIR - Wind direction (degrees clockwise from true N)
        6: WSPD - Wind speed (m/s)
        7: GST - Gust speed (m/s)
        """
        try:
            return NDBCWindData(
                direction=self._safe_float(data[5]) if len(data) > 5 else None,
                speed=self._safe_float(data[6]) if len(data) > 6 else None,
                gust=self._safe_float(data[7]) if len(data) > 7 else None
            )
        except (ValueError, IndexError):
            return NDBCWindData()
    
    def _parse_wave_data(self, data: list[str]) -> NDBCWaveData:
        """Parse NDBC wave fields into WaveData model.
        
        Field positions:
        8: WVHT - Significant wave height (meters)
        9: DPD - Dominant wave period (seconds)
        10: APD - Average wave period (seconds)
        11: MWD - Mean wave direction (degrees)
        """
        try:
            height = self._safe_float(data[8]) if len(data) > 8 else None
            period = self._safe_float(data[9]) if len(data) > 9 else None
            
            # Calculate wave steepness if we have both height and period
            steepness = None
            if height is not None and period is not None:
                steepness_ratio = height / (period * period)
                if steepness_ratio >= 0.025:
                    steepness = "VERY_STEEP"
                elif steepness_ratio >= 0.02:
                    steepness = "STEEP"
            
            return NDBCWaveData(
                height=height,
                period=period,
                direction=self._safe_float(data[11]) if len(data) > 11 else None,
                average_period=self._safe_float(data[10]) if len(data) > 10 else None,
                steepness=steepness
            )
        except (ValueError, IndexError):
            return NDBCWaveData()
    
    def _parse_met_data(self, data: list[str]) -> NDBCMetData:
        """Parse NDBC meteorological fields into MetData model.
        
        Field positions:
        12: PRES - Sea level pressure (hPa)
        13: ATMP - Air temperature (Celsius)
        14: WTMP - Water temperature (Celsius)
        15: DEWP - Dewpoint temperature (Celsius)
        16: VIS - Visibility (nautical miles)
        17: PTDY - Pressure tendency (hPa)
        18: TIDE - Water level (feet)
        """
        try:
            return NDBCMetData(
                pressure=self._safe_float(data[12]) if len(data) > 12 else None,
                air_temp=self._safe_float(data[13]) if len(data) > 13 else None,
                water_temp=self._safe_float(data[14]) if len(data) > 14 else None,
                dewpoint=self._safe_float(data[15]) if len(data) > 15 else None,
                visibility=self._safe_float(data[16]) if len(data) > 16 else None,
                pressure_tendency=self._safe_float(data[17]) if len(data) > 17 else None,
                water_level=self._safe_float(data[18]) if len(data) > 18 else None
            )
        except (ValueError, IndexError):
            return NDBCMetData()
    
    def _calculate_data_age(self, timestamp: datetime) -> NDBCDataAge:
        """Calculate age of data from timestamp."""
        age_minutes = (datetime.now(timezone.utc) - timestamp).total_seconds() / 60
        return NDBCDataAge(
            minutes=round(age_minutes, 1),
            isStale=age_minutes > 45
        ) 