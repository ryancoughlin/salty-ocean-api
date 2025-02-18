import logging
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import HTTPException

from features.tides.models.tide_types import (
    TideStation,
    TideStationPredictions,
    GeoJSONResponse,
    GeoJSONFeature,
    TidePrediction
)

logger = logging.getLogger(__name__)

class TideService:
    """Service for interacting with NOAA CO-OPS tide data API."""
    
    def __init__(self) -> None:
        """Initialize TideService."""
        self.data_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        self.stations_file = Path(__file__).parent.parent.parent.parent / "tide_stations.json"
        
    async def get_all_stations(self) -> List[TideStation]:
        """Get list of all tide stations."""
        try:
            stations = self._get_stations_from_file()
            return [
                TideStation(
                    id=station["station_id"],
                    name=station["name"],
                    location={
                        "lat": station["lat"],
                        "lng": station["lng"]
                    }
                )
                for station in stations
            ]
        except Exception as e:
            logger.error(f"Error getting tide stations: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_stations_geojson(self) -> GeoJSONResponse:
        """Get tide stations in GeoJSON format."""
        try:
            stations = self._get_stations_from_file()
            
            features = [
                GeoJSONFeature(
                    type="Feature",
                    geometry={
                        "type": "Point",
                        "coordinates": [station["lng"], station["lat"]]
                    },
                    properties={
                        "id": station["station_id"],
                        "name": station["name"],
                        "type": station["type"]
                    }
                )
                for station in stations
            ]
            
            return GeoJSONResponse(features=features)
            
        except Exception as e:
            logger.error(f"Error converting stations to GeoJSON: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_station_predictions(
        self,
        station_id: str,
        date: Optional[datetime] = None
    ) -> TideStationPredictions:
        """Get tide predictions for a specific station."""
        try:
            # Get station info
            stations = self._get_stations_from_file()
            station = next((s for s in stations if s["station_id"] == station_id), None)
            if not station:
                raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
            
            # Get predictions
            predictions_data = await self._get_predictions(
                station_id,
                start_date=date,
                end_date=date + timedelta(days=7) if date else None
            )
            
            predictions = [
                TidePrediction(
                    time=p["t"],
                    height=float(p["v"])
                )
                for p in predictions_data
            ]
            
            return TideStationPredictions(
                id=station_id,
                name=station["name"],
                predictions=predictions
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting predictions for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def _get_stations_from_file(self) -> List[Dict[str, Any]]:
        """Get list of tide stations from local JSON file."""
        try:
            with open(self.stations_file, 'r') as f:
                stations = json.load(f)
            
            return [
                {
                    "station_id": station["station_id"],
                    "name": station["name"],
                    "lat": station["latitude"],
                    "lng": station["longitude"],
                    "type": station["prediction_type"],
                    "state": None,
                    "timezone": None,
                    "affiliations": []
                }
                for station in stations
            ]
        except Exception as e:
            logger.error(f"Error reading tide stations from file: {str(e)}")
            raise

    async def _get_predictions(
        self,
        station_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get tide predictions for a station from NOAA CO-OPS API."""
        try:
            start_date = start_date or datetime.now()
            end_date = end_date or start_date + timedelta(days=7)

            params = {
                "begin_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "station": station_id,
                "product": "predictions",
                "datum": "MLLW",
                "time_zone": "lst_ldt",
                "interval": "hilo",
                "units": "english",
                "format": "json"
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.data_url,
                    params=params,
                    headers=headers,
                    timeout=30,
                    verify_ssl=False  # Disable SSL verification
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if "error" in data:
                        if "No Predictions data was found" in data["error"].get("message", ""):
                            # Return empty list for stations without prediction data
                            return []
                        else:
                            # Raise other API errors
                            raise Exception(data["error"].get("message", "Unknown error from NOAA API"))
                        
                    return data.get("predictions", [])
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching tide predictions for station {station_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error fetching tide predictions for station {station_id}: {str(e)}")
            raise 