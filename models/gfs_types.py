from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from geojson_pydantic import Point

class StationInfo(BaseModel):
    name: str
    location: Point
    type: str = "buoy"

class WaveComponent(BaseModel):
    height_m: float = Field(..., description="Wave height in meters")
    height_ft: float = Field(..., description="Wave height in feet")
    period: float = Field(..., description="Wave period in seconds")
    direction: float = Field(..., description="Wave direction in degrees")

class WaveForecast(BaseModel):
    timestamp: datetime = Field(..., description="Forecast timestamp in UTC")
    waves: List[WaveComponent] = Field(..., description="Wave components sorted by height")

class GFSCycle(BaseModel):
    date: str = Field(..., description="Model run date in YYYYMMDD format")
    hour: str = Field(..., description="Model run hour in HH format (UTC)")

class GFSWaveForecast(BaseModel):
    station_id: str
    station_info: StationInfo
    cycle: GFSCycle
    forecasts: List[WaveForecast] 