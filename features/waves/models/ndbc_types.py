from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from features.common.models.station_types import Location

class NDBCWindData(BaseModel):
    """NDBC wind measurements."""
    speed: Optional[float] = None  # m/s
    direction: Optional[float] = None  # degrees clockwise from true N
    gust: Optional[float] = None  # m/s

class NDBCWaveData(BaseModel):
    """NDBC wave measurements."""
    height: Optional[float] = None  # meters
    period: Optional[float] = None  # seconds
    direction: Optional[float] = None  # degrees
    average_period: Optional[float] = None  # seconds
    steepness: Optional[str] = None  # STEEP, VERY_STEEP, etc.

class NDBCMetData(BaseModel):
    """NDBC meteorological measurements."""
    pressure: Optional[float] = None  # hPa
    air_temp: Optional[float] = None  # Celsius
    water_temp: Optional[float] = None  # Celsius
    dewpoint: Optional[float] = None  # Celsius
    visibility: Optional[float] = None  # nautical miles
    pressure_tendency: Optional[float] = None  # hPa
    water_level: Optional[float] = None  # feet above/below MLLW

class NDBCDataAge(BaseModel):
    """Age of NDBC observation data."""
    minutes: float
    isStale: bool  # True if > 45 minutes old

class NDBCObservation(BaseModel):
    """Real-time observation from NDBC station."""
    time: datetime
    wind: NDBCWindData
    wave: NDBCWaveData
    met: NDBCMetData
    data_age: NDBCDataAge

class NDBCLocation(BaseModel):
    type: str = "Point"
    coordinates: List[float]

class NDBCStation(BaseModel):
    station_id: str
    name: str
    location: NDBCLocation
    observations: NDBCObservation 