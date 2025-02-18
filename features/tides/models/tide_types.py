from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

class TidePrediction(BaseModel):
    """Individual tide prediction"""
    time: str = Field(..., description="Time of prediction")
    height: float = Field(..., description="Height of tide in feet")

class StationLocation(BaseModel):
    """Station location in GeoJSON format"""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")

class TideStation(BaseModel):
    """Tide station details"""
    id: str = Field(..., description="Station identifier")
    name: str = Field(..., description="Station name")
    location: StationLocation = Field(..., description="Station location")

class TideStationPredictions(BaseModel):
    """Tide station with predictions"""
    id: str = Field(..., description="Station identifier")
    name: str = Field(..., description="Station name")
    predictions: List[TidePrediction] = Field(..., description="List of tide predictions")

class GeoJSONFeature(BaseModel):
    """GeoJSON Feature"""
    type: Literal["Feature"] = "Feature"
    geometry: dict = Field(..., description="GeoJSON geometry")
    properties: dict = Field(..., description="Feature properties")

class GeoJSONResponse(BaseModel):
    """GeoJSON FeatureCollection response"""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature] = Field(..., description="List of GeoJSON features") 