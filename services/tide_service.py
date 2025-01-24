import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from core.config import settings

logger = logging.getLogger(__name__)

class TideService:
    """Service for interacting with NOAA CO-OPS tide data API."""
    
    def __init__(self):
        """Initialize TideService."""
        self.base_url = settings.coops_base_url
        
    def get_stations(self) -> List[Dict[str, Any]]:
        """Get list of tide stations from NOAA CO-OPS API."""
        try:
            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching tide stations: {str(e)}")
            raise

    def get_predictions(
        self,
        station_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get tide predictions for a station from NOAA CO-OPS API."""
        try:
            # Default to 24 hours of predictions if no dates provided
            if not start_date:
                start_date = datetime.now()
            if not end_date:
                end_date = start_date + timedelta(days=1)

            params = {
                "station": station_id,
                "begin_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "product": "predictions",
                "datum": "MLLW",
                "units": "english",
                "time_zone": "lst_ldt",
                "format": "json"
            }

            response = requests.get(
                f"{self.base_url}/datagetter",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching tide predictions for station {station_id}: {str(e)}")
            raise 