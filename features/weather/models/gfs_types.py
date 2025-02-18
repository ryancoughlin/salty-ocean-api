from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from geojson_pydantic import Point

class StationInfo(BaseModel):
    """Station information for GFS forecasts."""
    name: str
    location: Point
    type: str = "buoy"

class WaveComponent(BaseModel):
    """Individual wave component in GFS forecast."""
    height_m: float = Field(..., description="Wave height in meters")
    height_ft: float = Field(..., description="Wave height in feet")
    period: float = Field(..., description="Wave period in seconds")
    direction: float = Field(..., description="Wave direction in degrees")

class WaveForecast(BaseModel):
    """Single point in GFS wave forecast."""
    timestamp: datetime = Field(..., description="Forecast timestamp in UTC")
    waves: List[WaveComponent] = Field(..., description="Wave components sorted by height")

class GFSCycle(BaseModel):
    """GFS model run information."""
    date: str = Field(..., description="Model run date in YYYYMMDD format")
    hour: str = Field(..., description="Model run hour in HH format (UTC)")

class GFSWaveForecast(BaseModel):
    """Complete GFS wave forecast for a station."""
    station_id: str
    station_info: StationInfo
    cycle: GFSCycle
    forecasts: List[WaveForecast] 