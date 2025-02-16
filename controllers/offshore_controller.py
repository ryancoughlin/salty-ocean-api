from typing import Dict, List
from fastapi import HTTPException
from services.ndbc_observation_service import NDBCObservationService
from services.wave_data_processor import WaveDataProcessor
from services.weather import WeatherSummaryService
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
    def __init__(self, prefetch_service: PrefetchService, weather_service: WeatherSummaryService, ndbc_observation_service: NDBCObservationService):
        self.prefetch_service = prefetch_service
        self.weather_service = weather_service
        self.ndbc_observation_service = ndbc_observation_service

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
        """Get real-time observations for a specific NDBC station.
        
        Args:
            station_id: The NDBC station identifier (e.g. "44098")
            
        Returns:
            NDBCStation: Station info with latest observations
            
        Raises:
            HTTPException: If station not found or error fetching data
        """
        try:
            # Get station metadata
            station = self._get_station(station_id)
            
            # Fetch latest observations
            raw_data = await self.ndbc_observation_service.get_realtime_observations(station_id)
            
            # Create observation model
            observation = NDBCObservation(
                time=raw_data['timestamp'],
                wind=WindData(**raw_data['wind']),
                wave=WaveData(**raw_data['wave'])
            )
            
            # Return complete station data
            return NDBCStation(
                station_id=station["id"],
                name=station["name"],
                location=Location(
                    type="Point", 
                    coordinates=station["location"]["coordinates"]
                ),
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
                current_obs = await self.ndbc_observation_service.get_realtime_observations(station_id)
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