from pydantic import BaseModel
from datetime import datetime
from typing import List

class WindData(BaseModel):
    """Single point of wind data."""
    timestamp: datetime
    wind_speed: float  # meters per second
    wind_gust: float  # meters per second
    wind_direction: float  # degrees from true north

class WindForecast(BaseModel):
    """Complete wind forecast for a station."""
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    forecasts: List[WindData] 