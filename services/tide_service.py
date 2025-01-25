import logging
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class TideService:
    """Service for interacting with NOAA CO-OPS tide data API."""
    
    def __init__(self) -> None:
        """Initialize TideService."""
        self.data_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        self.stations_file = Path(__file__).parent.parent / "tide_stations.json"
        
    def get_stations(self) -> List[Dict[str, Any]]:
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

    def get_predictions(
        self,
        station_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
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
                "application": "DataAPI_Sample",
                "format": "json"
            }

            response = requests.get(
                self.data_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise Exception(data["error"].get("message", "Unknown error from NOAA API"))
                
            return data.get("predictions", [])
        except Exception as e:
            logger.error(f"Error fetching tide predictions for station {station_id}: {str(e)}")
            raise 