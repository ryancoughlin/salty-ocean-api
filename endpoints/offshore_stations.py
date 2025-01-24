from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Path
from models.buoy import NDBCStation, NDBCObservation, NDBCForecastResponse
from services.buoy_service import BuoyService
from services.wave_data_processor import WaveDataProcessor
from services.weather_summary_service import WeatherSummaryService
import json
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
wave_processor = WaveDataProcessor()
buoy_service = BuoyService()
summary_service = WeatherSummaryService()

def load_stations():
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

@router.get(
    "/{station_id}/observations",
    response_model=NDBCStation,
    summary="Get real-time observations for a station",
    description="Returns the latest observations from NDBC for the specified station"
)
async def get_station_observations(
    station_id: str
) -> NDBCStation:
    """Get real-time observations for a specific NDBC station."""
    try:
        # Load stations data
        stations = load_stations()
        
        # Find requested station
        station = next(
            (s for s in stations if s["id"] == station_id),
            None
        )
        
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found"
            )
        
        # Get latest observations
        observation = buoy_service.get_realtime_observations(station_id)
        
        # Return combined station info and observations
        return NDBCStation(
            station_id=station["id"],
            name=station["name"],
            location=station["location"],
            observations=[NDBCObservation(**observation)]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching observations: {str(e)}"
        )

@router.get(
    "/{station_id}/forecast",
    response_model=NDBCForecastResponse,
    summary="Get wave forecast for a station",
    description="Returns the latest wave model forecast from NOAA for the specified station"
)
async def get_station_forecast(
    station_id: str
) -> NDBCForecastResponse:
    """Get wave model forecast for a specific station"""
    start_time = time.time()
    logger.info(f"Starting forecast request for station {station_id}")
    
    try:
        # Load stations data
        t0 = time.time()
        stations = load_stations()
        logger.debug(f"Loaded stations data in {time.time() - t0:.2f}s")
        
        # Find requested station
        station = next(
            (s for s in stations if s["id"] == station_id),
            None
        )
        
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found"
            )
        
        # Get current model run info
        t0 = time.time()
        model_run, date = wave_processor.get_current_model_run()
        logger.debug(f"Got model run info in {time.time() - t0:.2f}s: {date} {model_run}z")
        
        # Get forecast data
        t0 = time.time()
        forecast_data = wave_processor.process_station_forecast(station_id, model_run, date)
        logger.debug(f"Processed forecast data in {time.time() - t0:.2f}s")
        logger.debug(f"Forecast data contains {len(forecast_data['forecasts'])} entries")
        
        response = NDBCForecastResponse(
            station_id=station_id,
            name=station["name"],
            location=station["location"],
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

@router.get("/{station_id}/summary")
async def get_station_summary(station_id: str) -> Dict:
    """Get a summary for a specific station."""
    try:
        # Get forecast data from wave processor
        forecast_data = wave_processor.process_station_forecast(station_id)
        if not forecast_data or not forecast_data.get("forecasts"):
            raise HTTPException(status_code=404, detail="No forecast data available for station")

        # Generate summary from forecast data
        summary = summary_service.generate_summary(
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