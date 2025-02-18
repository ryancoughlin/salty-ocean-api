from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from features.common.models.station_types import Location, Station

class WaveForecastPoint(BaseModel):
    """Single point in a wave forecast."""
    time: datetime
    height: Optional[float] = None  # meters
    period: Optional[float] = None  # seconds
    direction: Optional[float] = None  # degrees

class WaveForecastResponse(BaseModel):
    """Complete wave forecast response for a station."""
    station: Station
    forecasts: List[WaveForecastPoint]
    model_run: str  # e.g. "20250218 06z" 