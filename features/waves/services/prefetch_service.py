import logging
from datetime import datetime
from typing import Dict, Optional
# from features.weather.services.gfs_wave_service import GFSWaveService
from features.waves.services.buoy_service import BuoyService
from features.stations.services.station_service import StationService
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
        # gfs_wave_service: GFSWaveService,
        buoy_service: BuoyService,
        station_service: Optional[StationService] = None
    ):
        # self.gfs_wave_service = gfs_wave_service
        self.buoy_service = buoy_service
        self.station_service = station_service
        self._cache: Dict[str, NDBCForecastResponse] = {}
        
    def get_station_forecast(self, station_id: str) -> Optional[NDBCForecastResponse]:
        """Get cached forecast for a station."""
        return self._cache.get(station_id)
        
    async def prefetch_all(self) -> None:
        """Prefetch forecasts for all stations."""
        try:
            if not self.station_service:
                logger.error("Station service not initialized")
                return
                
            stations = self.station_service.get_stations()
            if not stations:
                logger.warning("No stations found for prefetching")
                return
                
            for station in stations:
                station_id = station["id"]
                try:
                    # Debug log the station being processed
                    logger.info(f"Processing station {station_id}: {station['name']}")
                    
                    # Comment out GFS wave service calls for now
                    # forecast = await self.gfs_wave_service.get_station_forecast(station_id, station)
                    
                    # # Convert GFS forecast to NDBC format
                    # forecast_points = []
                    # for gfs_point in forecast.forecasts:
                    #     # Get primary wave component (highest)
                    #     primary_wave = gfs_point.waves[0] if gfs_point.waves else None
                    #     
                    #     forecast_points.append(
                    #         NDBCForecastPoint(
                    #             time=gfs_point.timestamp,
                    #             wave=NDBCWaveData(
                    #                 height=primary_wave.height_ft if primary_wave else None,
                    #                 period=primary_wave.period if primary_wave else None,
                    #                 direction=primary_wave.direction if primary_wave else None
                    #             )
                    #         )
                    #     )
                    # 
                    # self._cache[station_id] = NDBCForecastResponse(
                    #     station_id=station_id,
                    #     name=station["name"],
                    #     location=station["location"],
                    #     model_run=f"{forecast.cycle.date} {forecast.cycle.hour}z",
                    #     forecasts=forecast_points
                    # )
                    
                    logger.debug(f"Processed station {station_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing station {station_id}: {str(e)}")
                    
            logger.info(f"Processed {len(stations)} stations")
            
        except Exception as e:
            logger.error(f"Error prefetching forecasts: {str(e)}")
            raise 