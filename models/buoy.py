from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Location(BaseModel):
    type: str = "Point"
    coordinates: List[float]

class NDBCObservation(BaseModel):
    timestamp: datetime
    wind_dir: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_gust: Optional[float] = None
    wave_height: Optional[float] = None
    dominant_period: Optional[float] = None
    average_period: Optional[float] = None
    mean_wave_direction: Optional[float] = None
    pressure: Optional[float] = None
    air_temp: Optional[float] = None
    water_temp: Optional[float] = None
    dewpoint: Optional[float] = None
    visibility: Optional[float] = None
    pressure_tendency: Optional[float] = None
    tide: Optional[float] = None

class NDBCStation(BaseModel):
    station_id: str
    name: str
    location: Location
    observations: List[NDBCObservation]

class NDBCForecastResponse(BaseModel):
    station_id: str
    name: str
    location: Location
    model_run: str
    forecasts: List[dict] 