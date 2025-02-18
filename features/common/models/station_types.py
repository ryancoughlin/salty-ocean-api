from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class Location(BaseModel):
    """Station location in GeoJSON Point format."""
    type: str = "Point"
    coordinates: List[float]

class Station(BaseModel):
    """Common station information model."""
    station_id: str = Field(alias="id")  # Allow "id" from JSON to map to station_id
    name: str
    location: Location
    type: str = "buoy"  # Default to buoy type if not specified
    
    class Config:
        populate_by_name = True
        from_attributes = True

class WindData(BaseModel):
    """Wind measurements from model data."""
    speed: Optional[float] = None  # m/s
    direction: Optional[float] = None  # degrees clockwise from true N
    gust: Optional[float] = None  # m/s

class MetData(BaseModel):
    """Meteorological measurements."""
    pressure: Optional[float] = None  # hPa
    air_temp: Optional[float] = None  # Celsius
    water_temp: Optional[float] = None  # Celsius
    dewpoint: Optional[float] = None  # Celsius
    visibility: Optional[float] = None  # nautical miles
    pressure_tendency: Optional[float] = None  # hPa
    water_level: Optional[float] = None  # feet above/below MLLW

class DataAge(BaseModel):
    """Age of observation data."""
    minutes: float
    isStale: bool  # True if > 45 minutes old

class Observation(BaseModel):
    """Real-time observation from station."""
    time: datetime
    wind: WindData
    met: MetData
    data_age: DataAge