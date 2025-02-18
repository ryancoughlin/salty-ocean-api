from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel

class StationSummary(BaseModel):
    """Summary of station conditions and metadata."""
    station_id: str
    metadata: Dict
    summary: Optional[str]
    last_updated: datetime 