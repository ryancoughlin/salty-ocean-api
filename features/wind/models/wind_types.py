from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from features.common.models.station_types import Location

class WindData(BaseModel):
    """Wind data model."""
    speed: float
    direction: float
    gust: Optional[float] = None

class WindForecastPoint(BaseModel):
    """Single point in wind forecast."""
    time: datetime
    speed: float
    direction: float
    gust: Optional[float] = None

class WindForecastResponse(BaseModel):
    """Complete wind forecast response."""
    station_id: str
    name: str
    location: Location
    model_run: str
    forecasts: List[WindForecastPoint] 