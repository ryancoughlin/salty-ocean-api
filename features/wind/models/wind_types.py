from datetime import datetime
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from features.common.models.station_types import Station

class WindDirectionEnum(str, Enum):
    N = "North"
    NE = "Northeast"
    E = "East"
    SE = "Southeast"
    S = "South"
    SW = "Southwest"
    W = "West"
    NW = "Northwest"

class TrendTypeEnum(str, Enum):
    STEADY = "steady"
    BUILDING = "building"
    DROPPING = "dropping"
class WindDirectionModel(BaseModel):
    direction: WindDirectionEnum
    min_deg: float
    max_deg: float
    description: str

class WindForecastPoint(BaseModel):
    """Single point in wind forecast."""
    time: datetime
    speed: float = Field(..., description="Wind speed in mph")
    direction: float = Field(..., description="Degrees clockwise from true N")
    gust: Optional[float] = Field(None, description="Gust speed in mph")

class WindForecastResponse(BaseModel):
    """Complete wind forecast response."""
    station: Station
    model_run: str
    forecasts: List[WindForecastPoint]
    
    class Config:
        from_attributes = True 