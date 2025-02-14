import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json

from services.wave_data_processor import WaveDataProcessor
from repositories.station_repo import StationRepository
from core.config import settings
from pathlib import Path
from services.weather_summary_service import WeatherSummaryService

logger = logging.getLogger(__name__)

class PrefetchService:
    """Service for prefetching and caching wave model forecast data."""
    
    def __init__(self, wave_processor: WaveDataProcessor):
        self.wave_processor = wave_processor
        self.station_repo = StationRepository(Path('ndbcStations.json'))
        self.summary_service = WeatherSummaryService()
        self._forecast_cache = {}
        self._summary_cache = {}
        
    def get_station_forecast(self, station_id: str) -> Optional[Dict]:
        """Get cached forecast for a station."""
        return self._forecast_cache.get(station_id)
        
    def get_station_summary(self, station_id: str) -> Optional[Dict]:
        """Get cached summary for a station."""
        return self._summary_cache.get(station_id)
        
    async def prefetch_all(self) -> None:
        """Prefetch all station data."""
        try:
            start_time = datetime.now()
            
            # Get all stations
            stations = self.station_repo.load_stations()
            
            success_count = 0
            error_count = 0
            outside_grid_count = 0
            
            # Process each station
            for station in stations:
                station_id = station["id"]
                try:
                    # Get forecast
                    forecast = self.wave_processor.process_station_forecast(station_id)
                    
                    # Handle different response statuses
                    if forecast["status"] == "success":
                        # Cache forecast
                        self._forecast_cache[station_id] = forecast
                        
                        # Generate and cache summary
                        if forecast.get('forecasts'):
                            summary = self.summary_service.generate_summary(
                                forecast['forecasts'],
                                forecast['metadata']
                            )
                            self._summary_cache[station_id] = {
                                "station_id": station_id,
                                "metadata": forecast["metadata"],
                                "summary": summary
                            }
                        success_count += 1
                    elif forecast["status"] == "outside_grid":
                        outside_grid_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing station {station_id}: {str(e)}")
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Prefetch completed in {duration:.2f}s. "
                f"Success: {success_count}, "
                f"Outside Grid: {outside_grid_count}, "
                f"Failed: {error_count}"
            )
            
        except Exception as e:
            logger.error(f"Error during prefetch: {str(e)}")
            raise 