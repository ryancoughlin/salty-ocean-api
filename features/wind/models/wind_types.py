from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from features.common.models.station_types import Station

class WindForecastPoint(BaseModel):
    """Single point in wind forecast."""
    time: datetime
    speed: float  # mph
    direction: float # degrees clockwise from true N
    gust: Optional[float] = None  # mph

class WindForecastResponse(BaseModel):
    """Complete wind forecast response."""
    station: Station
    model_run: str
    forecasts: List[WindForecastPoint] 