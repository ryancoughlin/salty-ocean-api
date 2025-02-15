from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class Location(BaseModel):
    type: str = "Point"
    coordinates: List[float]

class WindData(BaseModel):
    speed: float
    direction: float

class WaveData(BaseModel):
    height: float
    period: float
    direction: float
    wind_height: Optional[float] = None
    wind_period: Optional[float] = None
    wind_direction: Optional[float] = None

class ForecastPoint(BaseModel):
    time: datetime
    wind: WindData
    wave: WaveData

class NDBCObservation(BaseModel):
    time: datetime
    wind: WindData
    wave: WaveData

class NDBCStation(BaseModel):
    station_id: str
    name: str
    location: Location
    observations: Optional["NDBCObservation"] = None

class NDBCForecastResponse(BaseModel):
    station_id: str
    name: str
    location: Location
    model_run: str
    forecasts: List[ForecastPoint]

class StationSummary(BaseModel):
    station_id: str
    metadata: Dict
    summary: Dict
    last_updated: datetime

class WeatherConditions(BaseModel):
    conditions: Optional[str]
    best_window: Optional[str] 