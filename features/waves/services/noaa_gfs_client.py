import logging
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field

from features.common.models.station_types import Station
from features.common.utils.conversions import UnitConversions
from core.config import settings
from core.cache import cached
from features.common.services.model_run_service import ModelRunService

logger = logging.getLogger(__name__)

# Internal GFS types - not exposed in API
class GFSWaveComponent(BaseModel):
    """Individual wave component in GFS forecast."""
    height_m: float = Field(..., description="Wave height in meters")
    height_ft: float = Field(..., description="Wave height in feet")
    period: float = Field(..., description="Wave period in seconds")
    direction: float = Field(..., description="Wave direction in degrees")

class GFSForecastPoint(BaseModel):
    """Single point in GFS wave forecast."""
    timestamp: datetime = Field(..., description="Forecast timestamp in UTC")
    waves: List[GFSWaveComponent] = Field(..., description="Wave components sorted by height")

class GFSModelCycle(BaseModel):
    """GFS model run information."""
    date: str = Field(..., description="Model run date in YYYYMMDD format")
    hour: str = Field(..., description="Model run hour in HH format (UTC)")

class GFSWaveForecast(BaseModel):
    """Complete GFS wave forecast for a station."""
    station_info: Station
    cycle: GFSModelCycle
    forecasts: List[GFSForecastPoint]

def create_wave_component(height_m: float, period: float, direction: float) -> GFSWaveComponent:
    """Create a wave component with height conversion."""
    return GFSWaveComponent(
        height_m=height_m,
        height_ft=UnitConversions.meters_to_feet(height_m),
        period=period,
        direction=direction
    )

def is_header_line(line: str) -> bool:
    """Check if line is a header or separator."""
    line = line.lower().strip()
    return (
        not line or 
        line.startswith("+") or 
        "day" in line or 
        "hour" in line or
        any(x in line for x in ["location", "model", "cycle", "time"])
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
        # Skip if parts contain non-numeric values
        if not all(part.strip().isdigit() for part in parts):
            return None
            
        days, hours = map(int, parts)
        # Calculate total hours from cycle start, but ensure we start from cycle time
        total_hours = (days * 24) + hours
        forecast_time = cycle_dt + timedelta(hours=total_hours)
        logger.debug(f"Parsed time parts: days={days}, hours={hours}, cycle={cycle_dt}, forecast={forecast_time}")
        return forecast_time
    except (ValueError, TypeError) as e:
        # Only log if parts look like they should be valid numbers
        if any(part.strip().isdigit() for part in parts):
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

def create_forecast(timestamp: datetime, wave_components: List[GFSWaveComponent]) -> Optional[GFSForecastPoint]:
    """Create a forecast with sorted wave components."""
    if not wave_components:
        return None
    return GFSForecastPoint(
        timestamp=timestamp,
        waves=sorted(wave_components, key=lambda x: x.height_m, reverse=True)
    )

def parse_bulletin_line(line: str, cycle_dt: datetime) -> Optional[GFSForecastPoint]:
    """Parse a single bulletin line into a forecast."""
    try:
        # Skip header lines early
        if is_header_line(line):
            return None
            
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
    forecasts: List[GFSForecastPoint],
    start_date: datetime,
    end_date: datetime
) -> List[GFSForecastPoint]:
    """Filter forecasts within date range and sort by timestamp."""
    return sorted(
        [f for f in forecasts if start_date <= f.timestamp < end_date],
        key=lambda x: x.timestamp
    )

class NOAAGFSClient:
    def __init__(self, model_run_service: ModelRunService):
        self._session: Optional[aiohttp.ClientSession] = None
        self.model_run_service = model_run_service
        
    async def _init_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

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

    def _parse_bulletin(self, bulletin_text: str, cycle_date: str, cycle_hour: str) -> List[GFSForecastPoint]:
        """Parse a GFS wave bulletin into a list of forecasts."""
        cycle_dt = datetime.strptime(f"{cycle_date} {cycle_hour}", "%Y%m%d %H")
        cycle_dt = cycle_dt.replace(tzinfo=timezone.utc)
        
        # Filter out headers and parse valid lines
        valid_lines = [line for line in bulletin_text.splitlines() if not is_header_line(line)]
        
        forecasts = []
        for line in valid_lines:
            forecast = parse_bulletin_line(line, cycle_dt)
            if forecast:
                forecasts.append(forecast)
        
        return forecasts

    @cached(namespace="gfs_wave_forecast")
    async def get_station_forecast(self, station_id: str, station: Station) -> GFSWaveForecast:
        """Get wave forecast for a specific station."""
        try:
            # Get current cycle
            cycle_date, cycle_hour = await self.model_run_service.get_latest_available_cycle()
            date = cycle_date.strftime("%Y%m%d")
            logger.debug(f"Using forecast cycle: {date} {cycle_hour}Z")
            
            # Get bulletin and parse forecasts from current cycle
            if not await self._check_cycle_availability(date, cycle_hour):
                raise Exception(f"Latest GFS cycle not yet available: {date} {cycle_hour}Z")
                
            bulletin = await self._get_station_bulletin(station_id, date, cycle_hour)
            if not bulletin:
                raise Exception(f"No forecast data found for station {station_id}")
                
            current_forecasts = self._parse_bulletin(bulletin, date, cycle_hour)
            if not current_forecasts:
                raise Exception(f"Failed to parse forecast data for station {station_id}")
            
            # Sort current forecasts by timestamp
            current_forecasts = sorted(current_forecasts, key=lambda x: x.timestamp)
            logger.debug(f"Current cycle has {len(current_forecasts)} forecasts")
            
            # If current cycle starts tomorrow, get today's data from previous cycle
            now = datetime.now(timezone.utc)
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if current_forecasts[0].timestamp.date() > today.date():
                logger.debug("Getting today's data from previous cycle")
                prev_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
                prev_hour = "18" if cycle_hour == "00" else f"{int(cycle_hour)-6:02d}"
                
                prev_bulletin = await self._get_station_bulletin(station_id, prev_date, prev_hour)
                if prev_bulletin:
                    prev_forecasts = self._parse_bulletin(prev_bulletin, prev_date, prev_hour)
                    if prev_forecasts:
                        prev_forecasts = filter_forecasts_by_date_range(
                            prev_forecasts,
                            today,
                            current_forecasts[0].timestamp
                        )
                        logger.debug(f"Added {len(prev_forecasts)} forecasts from previous cycle")
                        current_forecasts = prev_forecasts + current_forecasts
            
            return GFSWaveForecast(
                station_info=station,
                cycle=GFSModelCycle(date=date, hour=cycle_hour),
                forecasts=current_forecasts
            )
            
        except Exception as e:
            logger.error(f"Error getting forecast for station {station_id}: {str(e)}")
            raise
            
        finally:
            # Ensure we close the session
            await self.close() 