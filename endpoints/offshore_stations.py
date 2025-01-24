from typing import List, Optional
from fastapi import APIRouter, HTTPException, Path
from models.buoy import NDBCStation, NDBCObservation, NDBCForecastResponse
from services.buoy_service import BuoyService
from services.wave_data_processor import WaveDataProcessor
import json
from pathlib import Path

router = APIRouter()
wave_processor = WaveDataProcessor()
buoy_service = BuoyService()

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
        
        # Get current model run info
        model_run, date = wave_processor.get_current_model_run()
        
        # Get forecast data
        forecast_data = wave_processor.process_station_forecast(station_id, model_run, date)
        
        return NDBCForecastResponse(
            station_id=station_id,
            name=station["name"],
            location=station["location"],
            model_run=f"{date} {model_run}z",
            forecasts=forecast_data["forecasts"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 