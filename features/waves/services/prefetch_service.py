import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime
from features.waves.services.wave_data_processor import WaveDataProcessor
from features.waves.services.buoy_service import BuoyService
from features.stations.models.station_types import (
    NDBCStation,
    NDBCLocation,
    NDBCForecastResponse,
    NDBCForecastPoint,
    NDBCWindData,
    NDBCWaveData
)

logger = logging.getLogger(__name__)

class PrefetchService:
    """Service for prefetching and caching wave model forecast data."""
    
    def __init__(
        self,
        wave_processor: WaveDataProcessor,
        buoy_service: BuoyService
    ):
        self.wave_processor = wave_processor
        self.buoy_service = buoy_service
        self._cache: Dict[str, NDBCForecastResponse] = {}
        
    def get_station_forecast(self, station_id: str) -> Optional[NDBCForecastResponse]:
        """Get cached forecast for a station."""
        return self._cache.get(station_id)
        
    async def prefetch_all(self) -> None:
        """Prefetch forecasts for all stations."""
        try:
            stations = self.wave_processor.get_stations()
            if not stations:
                logger.warning("No stations found for prefetching")
                return
                
            # Process stations in parallel
            tasks = []
            for station in stations:
                task = asyncio.create_task(self._prefetch_station(station))
                tasks.append(task)
                
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            logger.info(f"Prefetched forecasts for {len(stations)} stations")
            
        except Exception as e:
            logger.error(f"Error prefetching forecasts: {str(e)}")
            raise
            
    async def _prefetch_station(self, station: Dict) -> None:
        """Prefetch forecast for a single station."""
        try:
            station_id = station["id"]
            
            # Get forecast points from wave model
            forecast_points = []
            for time, wave_data in self.wave_processor.get_station_forecast(station_id):
                forecast_points.append(
                    NDBCForecastPoint(
                        time=time,
                        wind=NDBCWindData(
                            speed=wave_data.get("wind_speed"),
                            direction=wave_data.get("wind_direction"),
                            gust=wave_data.get("wind_gust")
                        ),
                        wave=NDBCWaveData(
                            height=wave_data.get("wave_height"),
                            period=wave_data.get("wave_period"),
                            direction=wave_data.get("wave_direction")
                        )
                    )
                )
            
            # Create and cache forecast response
            self._cache[station_id] = NDBCForecastResponse(
                station_id=station_id,
                name=station["name"],
                location=NDBCLocation(
                    type="Point",
                    coordinates=station["location"]["coordinates"]
                ),
                model_run=datetime.now().strftime("%Y%m%d_%H"),
                forecasts=forecast_points
            )
            
            logger.debug(f"Prefetched forecast for station {station_id}")
            
        except Exception as e:
            logger.error(f"Error prefetching station {station.get('id', 'unknown')}: {str(e)}")
            # Don't raise - allow other stations to continue 