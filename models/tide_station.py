from pydantic import BaseModel

class TideStation(BaseModel):
    name: str
    station_id: str
    latitude: float
    longitude: float
    prediction_type: str  # "Subordinate" or "Harmonic" 