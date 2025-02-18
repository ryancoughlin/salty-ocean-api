from pydantic import BaseModel
from datetime import datetime
from typing import List
from features.common.models.station_types import StationInfo

class WindData(BaseModel):
    """Single point of wind data."""
    timestamp: datetime
    wind_speed: float  # meters per second
    wind_gust: float  # meters per second
    wind_direction: float  # degrees from true north

class WindForecastResponse(BaseModel):
    """Complete wind forecast for a station."""
    station: StationInfo
    forecasts: List[WindData] 