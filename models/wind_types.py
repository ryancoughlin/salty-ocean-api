from pydantic import BaseModel
from datetime import datetime
from typing import List

class WindData(BaseModel):
    timestamp: datetime
    wind_speed: float
    wind_gust: float
    wind_direction: float

class WindForecast(BaseModel):
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    forecasts: List[WindData] 