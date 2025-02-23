from datetime import datetime
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from features.common.models.station_types import Station

class BeaufortScaleEnum(str, Enum):
    CALM = "Calm"
    LIGHT_AIR = "Light Air"
    LIGHT_BREEZE = "Light Breeze"
    GENTLE_BREEZE = "Gentle Breeze"
    MODERATE_BREEZE = "Moderate Breeze"
    FRESH_BREEZE = "Fresh Breeze"
    STRONG_BREEZE = "Strong Breeze"
    NEAR_GALE = "Near Gale"
    GALE = "Gale"
    STRONG_GALE = "Strong Gale"
    STORM = "Storm"
    VIOLENT_STORM = "Violent Storm"
    HURRICANE = "Hurricane"

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

class BeaufortScaleModel(BaseModel):
    category: BeaufortScaleEnum
    min_speed: int
    max_speed: int
    description: str

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
    beaufort_scale: Optional[BeaufortScaleEnum] = None
    wind_direction: Optional[WindDirectionEnum] = None
    trend: Optional[TrendTypeEnum] = None

class WindForecastResponse(BaseModel):
    """Complete wind forecast response."""
    station: Station
    model_run: str
    forecasts: List[WindForecastPoint]
    
    class Config:
        from_attributes = True 