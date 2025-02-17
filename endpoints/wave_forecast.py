from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from pathlib import Path

from services.weather.gfs_wave_service import GFSWaveService
from models.gfs_types import GFSWaveForecast
from repositories.station_repo import StationRepository

router = APIRouter(
    prefix="/wave-forecast",
    tags=["Wave Forecast"]
)

def get_station_repo():
    """Dependency to create StationRepository instance."""
    return StationRepository(Path("ndbcStations.json"))

@router.get("/{station_id}", response_model=GFSWaveForecast)
async def get_wave_forecast(
    station_id: str,
    wave_service: GFSWaveService = Depends(GFSWaveService),
    station_repo: StationRepository = Depends(get_station_repo)
) -> GFSWaveForecast:
    """Get GFS wave forecast for a specific station.
    
    Args:
        station_id: NDBC station identifier
        
    Returns:
        GFSWaveForecast: Wave forecast data for the station
        
    Raises:
        HTTPException: If station not found or forecast data unavailable
    """
    try:
        # Get station info
        station = station_repo.get_station(station_id)
        if not station:
            raise HTTPException(
                status_code=404,
                detail=f"Station {station_id} not found in station database"
            )
            
        # Get forecast
        forecast = await wave_service.get_station_forecast(station_id, station)
        return forecast
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        elif "not yet available" in str(e).lower():
            raise HTTPException(status_code=503, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e)) 