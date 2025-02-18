import logging
from typing import Dict, List
from fastapi import HTTPException
from datetime import datetime

from features.stations.models.station_types import (
    NDBCStation,
    NDBCForecastResponse,
    StationSummary
)
from core.cache import cached
from features.waves.services.prefetch_service import PrefetchService
from features.waves.services.buoy_service import BuoyService
from features.weather.services.summary_service import WeatherSummaryService
from features.stations.services.station_service import StationService

logger = logging.getLogger(__name__)

class WaveService:
    def __init__(
        self, 
        prefetch_service: PrefetchService, 
        weather_service: WeatherSummaryService, 
        buoy_service: BuoyService,
        station_service: StationService
    ):
        self.prefetch_service = prefetch_service
        self.weather_service = weather_service
        self.buoy_service = buoy_service
        self.station_service = station_service

    @cached(namespace="wave_forecast")
    async def get_station_forecast(self, station_id: str) -> NDBCForecastResponse:
        """Get wave model forecast for a specific station."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
                
            forecast_data = self.prefetch_service.get_station_forecast(station_id)
            
            if not forecast_data:
                logger.error(f"No forecast data available for station {station_id}")
                raise HTTPException(
                    status_code=503,
                    detail="Forecast data not available. Please try again later."
                )
            
            return forecast_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="wave_summary")
    async def get_station_wave_summary(self, station_id: str) -> StationSummary:
        """Get a wave conditions summary for a specific station."""
        try:
            # Get forecast from cache
            forecast = self.prefetch_service.get_station_forecast(station_id)
            if not forecast or not forecast.forecasts:
                raise HTTPException(status_code=404, detail="No forecast available for station")

            # Generate fresh summary
            conditions = self.weather_service.generate_summary(
                [f.model_dump() for f in forecast.forecasts]
            )
            
            return StationSummary(
                station_id=station_id,
                metadata=forecast.metadata,
                summary=conditions,
                last_updated=datetime.now()
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating summary for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="wave_stations_geojson")
    async def get_stations_geojson(self) -> Dict:
        """Get all wave monitoring stations in GeoJSON format."""
        try:
            stations = self.station_service.get_all_stations()
            
            features = []
            for station in stations:
                feature = {
                    "type": "Feature",
                    "geometry": station["location"],
                    "properties": {
                        "id": station["id"],
                        "name": station["name"],
                    }
                }
                features.append(feature)
            
            return {
                "type": "FeatureCollection",
                "features": features
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error converting stations to GeoJSON: {str(e)}"
            ) 