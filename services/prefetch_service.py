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
from models.buoy import (
    NDBCForecastResponse,
    StationSummary,
    WeatherConditions,
    ForecastPoint
)

logger = logging.getLogger(__name__)

class PrefetchService:
    """Service for prefetching and caching wave model forecast data."""
    
    def __init__(self, wave_processor: WaveDataProcessor, buoy_service = None):
        self.wave_processor = wave_processor
        self.station_repo = StationRepository(Path('ndbcStations.json'))
        self.summary_service = WeatherSummaryService()
        self.buoy_service = buoy_service
        self._forecast_cache: Dict[str, NDBCForecastResponse] = {}
        
    def get_station_forecast(self, station_id: str) -> Optional[NDBCForecastResponse]:
        """Get cached forecast for a station."""
        return self._forecast_cache.get(station_id)
        
    async def get_station_summary(self, station_id: str) -> Optional[StationSummary]:
        """Generate a fresh summary for a station using latest data."""
        try:
            # Get forecast from cache
            forecast = self._forecast_cache.get(station_id)
            if not forecast or not forecast.forecasts:
                return None

            # Get current observations if available
            current_obs = None
            if self.buoy_service:
                try:
                    current_obs = await self.buoy_service.get_realtime_observations(station_id)
                except Exception as e:
                    logger.warning(f"Could not fetch observations for {station_id}: {str(e)}")

            # Generate fresh summary
            conditions = self.summary_service.generate_summary(
                forecast.forecasts,
                forecast.metadata,
                current_observations=current_obs
            )
            
            return StationSummary(
                station_id=station_id,
                metadata=forecast.metadata,
                summary=conditions.model_dump(),
                last_updated=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error generating summary for station {station_id}: {str(e)}")
            return None
        
    async def prefetch_all(self) -> None:
        """Prefetch all station forecast data."""
        try:
            start_time = datetime.now()
            stations = self.station_repo.load_stations()
            
            success_count = 0
            error_count = 0
            outside_grid_count = 0
            
            for station in stations:
                station_id = station["id"]
                try:
                    forecast = self.wave_processor.process_station_forecast(station_id)
                    
                    if forecast["status"] == "success":
                        self._forecast_cache[station_id] = NDBCForecastResponse(
                            station_id=station_id,
                            name=station["name"],
                            location=forecast["location"],
                            model_run=forecast["model_run"],
                            forecasts=[ForecastPoint(**f) for f in forecast["forecasts"]]
                        )
                        success_count += 1
                    elif forecast["status"] == "outside_grid":
                        outside_grid_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing station {station_id}: {str(e)}")
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Prefetch completed in {duration:.1f}s: {success_count} success, {error_count} errors, {outside_grid_count} outside grid")
            
        except Exception as e:
            logger.error(f"Error during prefetch: {str(e)}")
            raise 