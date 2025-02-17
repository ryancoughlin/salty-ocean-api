import json
import logging
from typing import Dict, List
from fastapi import HTTPException
from services.buoy_service import BuoyService
from services.weather.summary_service import WeatherSummaryService
from models.ndbc_types import (
    NDBCStation,
    NDBCForecastResponse,
    StationSummary,
    NDBCLocation,
)
from core.cache import cached
from core.config import settings
from services.prefetch_service import PrefetchService
from services.station_service import StationService
from datetime import datetime

logger = logging.getLogger(__name__)

class OffshoreController:
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
            observation = await self.buoy_service.get_observation(station_id)
            
            # Return complete station data
            return NDBCStation(
                station_id=station["id"],
                name=station["name"],
                location=NDBCLocation(
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

    @cached(namespace="offshore_data")
    async def get_station_data(self, station_id: str) -> NDBCForecastResponse:
        """Get current conditions and forecast for a station."""
        try:
            station = self.station_service.get_station(station_id)
            
            # Get current conditions
            current = await self.buoy_service.get_station_data(station_id)
            
            # Get forecast data
            forecast = await self.prefetch_service.get_station_forecast(station_id)
            
            # Generate summary
            summary = None
            if forecast and forecast.get("forecasts"):
                summary = self.weather_service.generate_summary(forecast["forecasts"])
            
            return NDBCForecastResponse(
                station=NDBCStation(
                    id=station_id,
                    name=station["name"],
                    location=NDBCLocation(
                        latitude=station["location"]["coordinates"][1],
                        longitude=station["location"]["coordinates"][0]
                    )
                ),
                current=current,
                forecast=forecast,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Error getting data for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing station data: {str(e)}"
            ) 