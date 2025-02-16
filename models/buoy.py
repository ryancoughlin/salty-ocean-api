from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class Location(BaseModel):
    type: str = "Point"
    coordinates: List[float]

class WindData(BaseModel):
    speed: Optional[float] = None
    direction: Optional[float] = None

class WaveData(BaseModel):
    height: Optional[float] = None
    period: Optional[float] = None
    direction: Optional[float] = None
    wind_height: Optional[float] = None
    wind_period: Optional[float] = None
    wind_direction: Optional[float] = None

class DataAge(BaseModel):
    minutes: float
    isStale: bool

class ForecastPoint(BaseModel):
    time: datetime
    wind: WindData
    wave: WaveData

class NDBCObservation(BaseModel):
    time: datetime
    wind: WindData
    wave: WaveData
    data_age: DataAge

class NDBCStation(BaseModel):
    station_id: str
    name: str
    location: Location
    observations: Optional[NDBCObservation] = None

class NDBCForecastResponse(BaseModel):
    station_id: str
    name: str
    location: Location
    model_run: str
    forecasts: List[ForecastPoint]
    
    @property
    def metadata(self) -> Dict:
        """Return metadata about this station."""
        return {
            "id": self.station_id,
            "name": self.name,
            "location": self.location.model_dump()
        }

class StationSummary(BaseModel):
    station_id: str
    metadata: Dict
    summary: Dict
    last_updated: datetime

class WeatherConditions(BaseModel):
    currentConditions: Optional[str] = None
    weeklyBest: Optional[str] = None
    overallConditions: Optional[str] = None 