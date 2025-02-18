from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel

from features.common.models.station_types import Location

class StationSummary(BaseModel):
    """Summary of station conditions and metadata."""
    station_id: str
    metadata: Dict
    summary: Optional[str]
    last_updated: datetime

class Station(BaseModel):
    """Station with metadata and latest observations."""
    station_id: str
    name: str
    location: Location
    observations: Optional[Dict] = None  # Temporarily make this a Dict until we refactor 