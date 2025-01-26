from typing import Dict, List
from fastapi import HTTPException
from services.buoy_service import BuoyService
from services.wave_data_processor import WaveDataProcessor
from services.weather_summary_service import WeatherSummaryService
from models.buoy import NDBCStation, NDBCObservation, NDBCForecastResponse, Location
from core.cache import cached
import json
import logging
import time

logger = logging.getLogger(__name__)

class OffshoreController:
    def __init__(self):
        self.wave_processor = WaveDataProcessor()
        self.buoy_service = BuoyService()
        self.summary_service = WeatherSummaryService()

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
            observation = self.buoy_service.get_realtime_observations(station_id)
            
            return NDBCStation(
                station_id=station["id"],
                name=station["name"],
                location=Location(type="Point", coordinates=station["location"]["coordinates"]),
                observations=[NDBCObservation(**observation)]
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching observations: {str(e)}"
            )

    @cached(namespace="wave_forecast", key_builder=lambda self, station_id, **_: f"{station_id}:{_.get('model_run', '')}")
    async def get_station_forecast(self, station_id: str) -> NDBCForecastResponse:
        """Get wave model forecast for a specific station"""
        start_time = time.time()
        logger.info(f"Starting forecast request for station {station_id}")
        
        try:
            station = self._get_station(station_id)
            
            t0 = time.time()
            model_run, date = self.wave_processor.get_current_model_run()
            logger.debug(f"Got model run info in {time.time() - t0:.2f}s: {date} {model_run}z")
            
            t0 = time.time()
            forecast_data = self.wave_processor.process_station_forecast(station_id)
            logger.debug(f"Processed forecast data in {time.time() - t0:.2f}s")
            logger.debug(f"Forecast data contains {len(forecast_data['forecasts'])} entries")
            
            response = NDBCForecastResponse(
                station_id=station_id,
                name=station["name"],
                location=Location(type="Point", coordinates=station["location"]["coordinates"]),
                model_run=f"{date} {model_run}z",
                forecasts=forecast_data["forecasts"]
            )
            
            total_time = time.time() - start_time
            logger.info(f"Completed forecast request for station {station_id} in {total_time:.2f}s")
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing forecast for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="station_summary")
    async def get_station_summary(self, station_id: str) -> Dict:
        """Get a summary for a specific station."""
        try:
            forecast_data = self.wave_processor.process_station_forecast(station_id)
            if not forecast_data or not forecast_data.get("forecasts"):
                raise HTTPException(status_code=404, detail="No forecast data available for station")

            summary = self.summary_service.generate_summary(
                forecasts=forecast_data["forecasts"],
                station_metadata=forecast_data["metadata"]
            )

            return {
                "station_id": station_id,
                "metadata": forecast_data["metadata"],
                "summary": summary
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
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