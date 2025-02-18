from pydantic import BaseModel
from typing import List

class Location(BaseModel):
    """Station location in GeoJSON Point format."""
    type: str = "Point"
    coordinates: List[float]

class StationInfo(BaseModel):
    """Common station information model."""
    id: str
    name: str
    location: Location 