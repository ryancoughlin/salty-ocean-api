from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import aiohttp
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from models.gfs_types import GFSWaveForecast, GFSCycle, WaveForecast, WaveComponent, StationInfo
from services.station_service import StationService
from services.weather.gfs_wave_service import GFSWaveService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/wave-forecast",
    tags=["Wave Forecast"]
)

def get_station_service():
    """Dependency to create StationService instance."""
    return StationService()

class GFSWaveClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.base_url = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
        
    async def _init_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _find_latest_cycle(self) -> tuple[str, str]:
        """Find the latest available GFS cycle.
        
        Returns:
            Tuple[str, str]: (date in YYYYMMDD format, hour in HH format)
        """
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour
        
        # Find most recent cycle (00/06/12/18Z)
        cycle_hour = (current_hour // 6) * 6
        cycle_date = current_time
        
        # GFS data is typically available ~5-6 hours after cycle start
        hours_since_cycle = current_hour - cycle_hour
        if hours_since_cycle < 6:
            # Go back to previous cycle
            if cycle_hour == 0:
                cycle_date = current_time - timedelta(days=1)
                cycle_hour = 18
            else:
                cycle_hour -= 6
                
        logger.info(f"Current time: {current_time}, Selected cycle: {cycle_date.strftime('%Y%m%d')} {cycle_hour:02d}Z")
        return cycle_date.strftime("%Y%m%d"), f"{cycle_hour:02d}"

    async def _check_cycle_availability(self, date: str, hour: str) -> bool:
        """Check if a GFS cycle is available."""
        session = await self._init_session()
        url = f"{self.base_url}/gfs.{date}/{hour}/wave/station/bulls.t{hour}z/gfswave.44098.bull"
        
        try:
            async with session.head(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Error checking cycle availability: {str(e)}")
            return False

    async def _get_station_bulletin(self, station_id: str, date: str, hour: str) -> Optional[str]:
        """Fetch the wave bulletin for a specific station."""
        session = await self._init_session()
        url = f"{self.base_url}/gfs.{date}/{hour}/wave/station/bulls.t{hour}z/gfswave.{station_id}.bull"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning(f"Failed to fetch bulletin for station {station_id}: HTTP {response.status}")
                return None
        except Exception as e:
            logger.error(f"Error fetching bulletin for station {station_id}: {str(e)}")
            return None

    def _parse_bulletin(self, bulletin_text: str, cycle_date: str, cycle_hour: str) -> List[WaveForecast]:
        """Parse a GFS wave bulletin into a list of forecasts."""
        cycle_dt = datetime.strptime(f"{cycle_date} {cycle_hour}", "%Y%m%d %H")
        cycle_dt = cycle_dt.replace(tzinfo=timezone.utc)
        
        forecasts = []
        for line in bulletin_text.splitlines():
            # Skip headers and empty lines
            if (not line or 
                line.startswith("+") or 
                line.startswith("|") and ("day" in line.lower() or "hour" in line.lower()) or
                any(x in line for x in ["Location", "Model", "Cycle"])):
                continue
                
            try:
                # Clean and split line
                parts = [p.strip() for p in line.strip().strip("|").split("|")]
                if len(parts) < 3:
                    continue
                    
                # Parse time - split on whitespace and handle both space and tab delimiters
                time_parts = [x for x in parts[0].strip().split() if x.strip()]
                if len(time_parts) != 2:
                    continue
                    
                # Parse days and hours
                try:
                    days, hours = map(int, time_parts)
                    total_hours = (days * 24) + hours
                    timestamp = cycle_dt + timedelta(hours=total_hours)
                except (ValueError, TypeError):
                    continue
                    
                # Parse wave components
                wave_components = []
                for component in parts[2:]:
                    if not component.strip():
                        continue
                    try:
                        values = component.replace("*", "").strip().split()
                        if len(values) != 3:
                            continue
                        height_m, period, direction = map(float, values)
                        wave_components.append(WaveComponent(
                            height_m=height_m,
                            height_ft=height_m * 3.28084,
                            period=period,
                            direction=direction
                        ))
                    except (ValueError, IndexError):
                        continue
                        
                if wave_components:
                    forecasts.append(WaveForecast(
                        timestamp=timestamp,
                        waves=sorted(wave_components, key=lambda x: x.height_m, reverse=True)
                    ))
                    
            except Exception as e:
                logger.warning(f"Error parsing bulletin line: {str(e)}")
                continue
                
        return sorted(forecasts, key=lambda x: x.timestamp)

    async def get_station_forecast(self, station_id: str, station_info: Dict) -> GFSWaveForecast:
        """Get wave forecast for a specific station."""
        try:
            # Get current cycle
            date, hour = self._find_latest_cycle()
            logger.info(f"Using forecast cycle: {date} {hour}Z")
            
            # Check cycle availability
            if not await self._check_cycle_availability(date, hour):
                raise HTTPException(
                    status_code=503,
                    detail=f"Latest GFS cycle not yet available. Attempted: {date} {hour}Z. Current time: {datetime.now(timezone.utc).strftime('%Y%m%d %HZ')}"
                )
                
            # Get bulletin
            bulletin = await self._get_station_bulletin(station_id, date, hour)
            if not bulletin:
                raise HTTPException(
                    status_code=404,
                    detail=f"No forecast data found for station {station_id}"
                )
                
            # Parse forecasts
            forecasts = self._parse_bulletin(bulletin, date, hour)
            if not forecasts:
                raise HTTPException(
                    status_code=404,
                    detail=f"Failed to parse forecast data for station {station_id}"
                )
                
            # Filter to 3-hour intervals after first 120 hours
            filtered_forecasts = []
            for i, forecast in enumerate(forecasts):
                hours_from_cycle = (forecast.timestamp - datetime.strptime(f"{date} {hour}", "%Y%m%d %H").replace(tzinfo=timezone.utc)).total_seconds() / 3600
                if hours_from_cycle <= 120 or i % 3 == 0:
                    filtered_forecasts.append(forecast)
            
            return GFSWaveForecast(
                station_id=station_id,
                station_info=StationInfo(
                    name=station_info["name"],
                    location=station_info["location"],
                    type=station_info.get("type", "buoy")
                ),
                cycle=GFSCycle(
                    date=date,
                    hour=hour
                ),
                forecasts=filtered_forecasts
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to fetch forecast: {str(e)}"
            )
        finally:
            await self.close()

@router.get(
    "/{station_id}",
    response_model=GFSWaveForecast,
    summary="Get GFS wave forecast for a station",
    description="Returns wave forecast data from the latest GFS model run for the specified station"
)
async def get_wave_forecast(
    station_id: str,
    station_service: StationService = Depends(get_station_service)
) -> GFSWaveForecast:
    """Get GFS wave forecast for a specific station.
    
    Args:
        station_id: NDBC station identifier
        
    Returns:
        GFSWaveForecast: Wave forecast data for the station
        
    Raises:
        HTTPException: If station not found or forecast data unavailable
    """
    # Get station info
    station = station_service.get_station(station_id)
    if not station:
        raise HTTPException(
            status_code=404,
            detail=f"Station {station_id} not found in station database"
        )
        
    # Get forecast
    client = GFSWaveClient()
    return await client.get_station_forecast(station_id, station)

# Mark old endpoint as deprecated
@router.get(
    "/old/{station_id}",
    response_model=GFSWaveForecast,
    deprecated=True,
    summary="[DEPRECATED] Get GFS wave forecast for a station",
    description="This endpoint is deprecated. Please use /wave-forecast/{station_id} instead."
)
async def get_wave_forecast_deprecated(
    station_id: str,
    wave_service: GFSWaveService = Depends(GFSWaveService),
    station_service: StationService = Depends(get_station_service)
) -> GFSWaveForecast:
    """[DEPRECATED] Get GFS wave forecast for a specific station.
    
    This endpoint is deprecated. Please use /wave-forecast/{station_id} instead.
    """
    try:
        # Get station info
        station = station_service.get_station(station_id)
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