from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel

class WaveData(BaseModel):
    """Wave data component for API response."""
    height: float
    period: float
    direction: float

class ForecastPoint(BaseModel):
    """Single forecast point for API response."""
    time: datetime
    wave: WaveData

class WaveForecastResponse(BaseModel):
    """API response model for wave forecasts."""
    station_id: str
    name: str
    location: Dict
    model_run: str
    forecasts: List[ForecastPoint]

class StationSummary(BaseModel):
    """Summary of station conditions and metadata."""
    station_id: str
    metadata: Dict
    summary: Optional[str]
    last_updated: datetime 