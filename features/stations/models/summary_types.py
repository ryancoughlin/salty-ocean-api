from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel
from features.common.models.station_types import Station

class StationSummary(BaseModel):
    """Summary of station conditions and metadata."""
    station_id: str
    summary: Optional[str]
    last_updated: datetime

class ConditionSummaryResponse(BaseModel):
    """Response model for station condition summaries."""
    station: Station
    summary: str
    generated_at: datetime

    class Config:
        from_attributes = True 