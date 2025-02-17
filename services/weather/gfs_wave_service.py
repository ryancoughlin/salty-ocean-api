import logging
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Tuple, Callable
from pathlib import Path
from itertools import groupby
from operator import attrgetter
from functools import partial

from models.gfs_types import GFSWaveForecast, GFSCycle, WaveForecast, WaveComponent, StationInfo
from core.config import settings

logger = logging.getLogger(__name__)

def create_wave_component(height_m: float, period: float, direction: float) -> WaveComponent:
    """Create a wave component with height conversion."""
    return WaveComponent(
        height_m=height_m,
        height_ft=height_m * 3.28084,
        period=period,
        direction=direction
    )

def parse_time_parts(parts: List[str], cycle_dt: datetime) -> Optional[datetime]:
    """Parse forecast time parts into datetime.
    
    Args:
        parts: List containing [days, hours] from the bulletin
        cycle_dt: The cycle start datetime
        
    Returns:
        datetime: The forecast timestamp, or None if parsing fails
    """
    try:
        days, hours = map(int, parts)
        # Calculate total hours from cycle start, but ensure we start from cycle time
        total_hours = (days * 24) + hours
        forecast_time = cycle_dt + timedelta(hours=total_hours)
        logger.debug(f"Parsed time parts: days={days}, hours={hours}, cycle={cycle_dt}, forecast={forecast_time}")
        return forecast_time
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing time parts {parts}: {str(e)}")
        return None

def parse_wave_values(component: str) -> Optional[Tuple[float, float, float]]:
    """Parse wave component values."""
    try:
        values = component.replace("*", "").strip().split()
        if len(values) != 3:
            return None
        return tuple(map(float, values))
    except (ValueError, IndexError):
        return None

def create_forecast(timestamp: datetime, wave_components: List[WaveComponent]) -> Optional[WaveForecast]:
    """Create a forecast with sorted wave components."""
    if not wave_components:
        return None
    return WaveForecast(
        timestamp=timestamp,
        waves=sorted(wave_components, key=lambda x: x.height_m, reverse=True)
    )

def is_header_line(line: str) -> bool:
    """Check if line is a header or separator."""
    return (not line or 
            line.startswith("+") or 
            line.startswith("|") and ("day" in line.lower() or "hour" in line.lower()) or
            any(x in line for x in ["Location", "Model", "Cycle"]))

def parse_bulletin_line(line: str, cycle_dt: datetime) -> Optional[WaveForecast]:
    """Parse a single bulletin line into a forecast."""
    try:
        # Clean and split line
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 3:
            return None
            
        # Parse time - split on whitespace and handle both space and tab delimiters
        time_parts = [x for x in parts[0].strip().split() if x.strip()]
        if len(time_parts) != 2:
            return None
            
        # Get forecast timestamp
        timestamp = parse_time_parts(time_parts, cycle_dt)
        if not timestamp:
            return None
            
        # Parse wave components
        wave_components = []
        for component in parts[2:]:
            if not component.strip():
                continue
            values = parse_wave_values(component)
            if values:
                height_m, period, direction = values
                wave_components.append(create_wave_component(height_m, period, direction))
                
        return create_forecast(timestamp, wave_components)
        
    except Exception as e:
        logger.warning(f"Error parsing bulletin line: {str(e)}")
        return None

def filter_forecasts_by_date_range(
    forecasts: List[WaveForecast],
    start_date: datetime,
    end_date: datetime
) -> List[WaveForecast]:
    """Filter forecasts within date range and sort by timestamp."""
    return sorted(
        [f for f in forecasts if start_date <= f.timestamp < end_date],
        key=lambda x: x.timestamp
    )

class GFSWaveService:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _init_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _find_latest_cycle(self) -> Tuple[str, str]:
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
        """Check if a GFS cycle is available by attempting to access a test file."""
        session = await self._init_session()
        url = f"{settings.gfs_wave_base_url}/gfs.{date}/{hour}/wave/station/bulls.t{hour}z/gfswave.44098.bull"
        
        try:
            async with session.head(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Error checking cycle availability: {str(e)}")
            return False

    async def _get_station_bulletin(self, station_id: str, date: str, hour: str) -> Optional[str]:
        """Fetch the wave bulletin for a specific station."""
        session = await self._init_session()
        url = f"{settings.gfs_wave_base_url}/gfs.{date}/{hour}/wave/station/bulls.t{hour}z/gfswave.{station_id}.bull"
        
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
        
        logger.info(f"Parsing bulletin for cycle {cycle_dt}")
        logger.info(f"First 5 lines of bulletin:\n" + "\n".join(bulletin_text.splitlines()[:5]))
        
        # Filter out headers and parse valid lines
        valid_lines = [line for line in bulletin_text.splitlines() if not is_header_line(line)]
        logger.info(f"First valid line: {valid_lines[0] if valid_lines else 'No valid lines'}")
        
        forecasts = []
        for line in valid_lines:
            forecast = parse_bulletin_line(line, cycle_dt)
            if forecast:
                forecasts.append(forecast)
                if len(forecasts) <= 2:  # Log first two forecasts for debugging
                    logger.info(f"Parsed forecast: {forecast.timestamp}")
        
        return forecasts

    async def get_station_forecast(self, station_id: str, station_info: Dict) -> GFSWaveForecast:
        """Get wave forecast for a specific station."""
        try:
            # Get current cycle
            date, hour = self._find_latest_cycle()
            logger.info(f"Using forecast cycle: {date} {hour}Z")
            
            # Get bulletin and parse forecasts from current cycle
            if not await self._check_cycle_availability(date, hour):
                raise Exception(f"Latest GFS cycle not yet available: {date} {hour}Z")
                
            bulletin = await self._get_station_bulletin(station_id, date, hour)
            if not bulletin:
                raise Exception(f"No forecast data found for station {station_id}")
                
            current_forecasts = self._parse_bulletin(bulletin, date, hour)
            if not current_forecasts:
                raise Exception(f"Failed to parse forecast data for station {station_id}")
            
            # Sort current forecasts by timestamp
            current_forecasts = sorted(current_forecasts, key=lambda x: x.timestamp)
            logger.info(f"Current cycle has {len(current_forecasts)} forecasts from {current_forecasts[0].timestamp} to {current_forecasts[-1].timestamp}")
            
            # If current cycle starts tomorrow, get today's data from previous cycle
            now = datetime.now(timezone.utc)
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if current_forecasts[0].timestamp.date() > today.date():
                logger.info("Current cycle starts tomorrow, getting today's data from previous cycle")
                prev_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                prev_hour = "18" if hour == "00" else f"{int(hour)-6:02d}"
                
                prev_bulletin = await self._get_station_bulletin(station_id, prev_date, prev_hour)
                if prev_bulletin:
                    prev_forecasts = self._parse_bulletin(prev_bulletin, prev_date, prev_hour)
                    if prev_forecasts:
                        prev_forecasts = sorted(prev_forecasts, key=lambda x: x.timestamp)
                        logger.info(f"Previous cycle has {len(prev_forecasts)} forecasts from {prev_forecasts[0].timestamp} to {prev_forecasts[-1].timestamp}")
                        
                        # Get forecasts from previous cycle that are for today
                        todays_forecasts = [f for f in prev_forecasts 
                                          if f.timestamp.date() == today.date() 
                                          and f.timestamp < current_forecasts[0].timestamp]
                        if todays_forecasts:
                            logger.info(f"Adding {len(todays_forecasts)} forecasts from previous cycle for today")
                            current_forecasts = todays_forecasts + current_forecasts
            
            # Ensure we only return 7 days of forecasts
            end_date = today + timedelta(days=7)
            filtered_forecasts = [f for f in current_forecasts if f.timestamp < end_date]
            
            logger.info(f"Final forecast set: {len(filtered_forecasts)} forecasts from {filtered_forecasts[0].timestamp} to {filtered_forecasts[-1].timestamp}")
            
            return GFSWaveForecast(
                station_id=station_id,
                station_info=StationInfo(**station_info),
                cycle=GFSCycle(date=date, hour=hour),
                forecasts=filtered_forecasts
            )
            
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise
            
        finally:
            # Ensure we close the session
            await self.close() 