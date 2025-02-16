from typing import Dict, List
from fastapi import HTTPException
from services.buoy_service import BuoyService
from services.wave_data_processor import WaveDataProcessor
from services.weather_summary_service import WeatherSummaryService
from models.buoy import (
    NDBCStation,
    NDBCForecastResponse,
    StationSummary,
    Location,
    NDBCObservation,
    WindData,
    WaveData
)
from core.cache import cached
import json
import logging
import time
from core.config import settings
from services.prefetch_service import PrefetchService
from datetime import datetime

logger = logging.getLogger(__name__)

class OffshoreController:
    def __init__(self, prefetch_service: PrefetchService, weather_service: WeatherSummaryService, buoy_service: BuoyService):
        self.prefetch_service = prefetch_service
        self.weather_service = weather_service
        self.buoy_service = buoy_service

    def _load_stations(self):
        """Load NDBC stations from JSON file."""
        try:
            stations_file = "ndbcStations.json"
            with open(stations_file) as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading station data: {str(e)}"
            )

    def _get_station(self, station_id: str) -> Dict:
        """Get station by ID."""
        stations = self._load_stations()
        station = next(
            (s for s in stations if s["id"] == station_id),
            None
        )
        
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found"
            )
        return station

    @cached(namespace="ndbc_observations")
    async def get_station_observations(self, station_id: str) -> NDBCStation:
        """Get real-time observations for a specific NDBC station."""
        try:
            station = self._get_station(station_id)
            raw_observation = await self.buoy_service.get_realtime_observations(station_id)
            
            # Transform raw observation into proper model structure
            observation = NDBCObservation(
                time=raw_observation['timestamp'],
                wind=WindData(
                    speed=raw_observation.get('wind_speed'),
                    direction=raw_observation.get('wind_dir')
                ),
                wave=WaveData(
                    height=raw_observation.get('wave_height'),
                    period=raw_observation.get('dominant_period'),
                    direction=raw_observation.get('mean_wave_direction')
                )
            )
            
            return NDBCStation(
                station_id=station["id"],
                name=station["name"],
                location=Location(type="Point", coordinates=station["location"]["coordinates"]),
                observations=observation
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching observations: {str(e)}"
            )

    @cached(namespace="wave_forecast")
    async def get_station_forecast(self, station_id: str) -> NDBCForecastResponse:
        """Get wave model forecast for a specific station."""
        try:
            station = self._get_station(station_id)
            forecast_data = self.prefetch_service.get_station_forecast(station_id)
            
            if not forecast_data:
                logger.error(f"No forecast data available for station {station_id}")
                raise HTTPException(
                    status_code=503,
                    detail="Forecast data not available. Please try again later."
                )
            
            return forecast_data  # Already in correct type from prefetch service
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="station_summary")
    async def get_station_summary(self, station_id: str) -> StationSummary:
        """Get a summary for a specific station."""
        try:
            # Get forecast from cache
            forecast = self.prefetch_service.get_station_forecast(station_id)
            if not forecast or not forecast.forecasts:
                raise HTTPException(status_code=404, detail="No forecast available for station")

            # Get current observations if available
            current_obs = None
            try:
                current_obs = await self.buoy_service.get_realtime_observations(station_id)
            except Exception as e:
                logger.warning(f"Could not fetch observations for {station_id}: {str(e)}")

            # Generate fresh summary
            conditions = self.weather_service.generate_summary(
                [f.model_dump() for f in forecast.forecasts],
                forecast.metadata,
                current_observations=current_obs
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

    @cached(namespace="stations_geojson")
    async def get_stations_geojson(self) -> Dict:
        """Convert NDBC stations to GeoJSON format."""
        try:
            stations = self._load_stations()
            
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
            
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            
            return geojson
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error converting stations to GeoJSON: {str(e)}"
            ) 