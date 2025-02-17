from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel

class NDBCLocation(BaseModel):
    """NDBC station location in GeoJSON Point format."""
    type: str = "Point"
    coordinates: List[float]

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

class NDBCStation(BaseModel):
    """NDBC station with metadata and latest observations."""
    station_id: str
    name: str
    location: NDBCLocation
    observations: Optional[NDBCObservation] = None

class NDBCForecastPoint(BaseModel):
    """Single point in NDBC wave model forecast."""
    time: datetime
    wind: NDBCWindData
    wave: NDBCWaveData

class NDBCForecastResponse(BaseModel):
    """Complete NDBC station forecast response."""
    station_id: str
    name: str
    location: NDBCLocation
    model_run: str
    forecasts: List[NDBCForecastPoint]
    
    @property
    def metadata(self) -> Dict:
        """Return metadata about this station."""
        return {
            "id": self.station_id,
            "name": self.name,
            "location": self.location.model_dump()
        }

class StationSummary(BaseModel):
    """Summary of station conditions and metadata."""
    station_id: str
    metadata: Dict
    summary: Optional[str]
    last_updated: datetime 