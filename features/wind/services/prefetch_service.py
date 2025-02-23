import logging
import asyncio
from typing import List
from pathlib import Path
import json

from features.common.models.station_types import Station, Location
from features.wind.services.gfs_wind_client import GFSWindClient
from features.common.services.model_run_service import ModelRun

logger = logging.getLogger(__name__)

class WindPrefetchService:
    """Service to prefetch wind forecast data for all stations."""
    
    def __init__(
        self,
        gfs_client: GFSWindClient,
        stations_file: Path = Path("ndbcStations.json")
    ):
        self.gfs_client = gfs_client
        self.stations_file = stations_file
        
    def _load_stations(self) -> List[Station]:
        """Load all stations from JSON file."""
        try:
            with open(self.stations_file) as f:
                stations_data = json.load(f)
                return [
                    Station(
                        station_id=station["id"],
                        name=station["name"],
                        location=Location(
                            type="Point",
                            coordinates=list(station["location"]["coordinates"])
                        ),
                        type=station.get("type", "buoy")
                    )
                    for station in stations_data
                ]
        except Exception as e:
            logger.error(f"Error loading stations for prefetch: {str(e)}")
            return []

    def _get_forecast_hours(self) -> List[int]:
        """Get list of forecast hours based on GFS file availability pattern."""
        # Every 3 hours from 0 to 384
        return list(range(0, 385, 3))
            
    async def prefetch_station_data(self, station: Station) -> bool:
        """Prefetch wind forecast data for a single station."""
        try:
            logger.info(f"Prefetching wind data for station {station.station_id}")
            forecast_hours = self._get_forecast_hours()
            logger.info(f"Downloading {len(forecast_hours)} forecast files for station {station.station_id}")
            
            await self.gfs_client.get_station_wind_forecast(station)
            # Add delay after successful download
            await asyncio.sleep(30)
            return True
        except Exception as e:
            logger.error(f"Error prefetching wind data for station {station.station_id}: {str(e)}")
            # Still add delay even if download failed to maintain rate limit
            await asyncio.sleep(30)
            return False
            
    async def prefetch_all_stations(self):
        """Prefetch wind forecast data for all stations sequentially."""
        if not self.gfs_client.model_run:
            logger.error("No model run available for prefetch")
            return
            
        stations = self._load_stations()
        if not stations:
            logger.error("No stations loaded for prefetch")
            return
            
        logger.info(f"Starting sequential wind data prefetch for {len(stations)} stations")
        
        successes = 0
        failures = 0
        
        # Process stations sequentially
        for station in stations:
            try:
                result = await self.prefetch_station_data(station)
                if result:
                    successes += 1
                else:
                    failures += 1
            except Exception as e:
                logger.error(f"Error processing station {station.station_id}: {str(e)}")
                failures += 1
                # Maintain delay even on error
                await asyncio.sleep(30)
                continue
        
        logger.info(f"Completed wind data prefetch. Successes: {successes}, Failures: {failures}")
        
    async def handle_model_run_update(self, model_run: ModelRun):
        """Handle model run update by prefetching new data."""
        logger.info(f"Handling model run update for wind prefetch: {model_run}")
        self.gfs_client.update_model_run(model_run)
        await self.prefetch_all_stations() 