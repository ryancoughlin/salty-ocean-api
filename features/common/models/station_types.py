from pydantic import BaseModel
from geojson_pydantic import Point

class StationInfo(BaseModel):
    """Station information used across all endpoints."""
    name: str
    location: Point
    type: str = "buoy" 