import aiohttp
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional, List
from core.config import settings

logger = logging.getLogger(__name__)

class BuoyService:
    """Service for interacting with NDBC buoy data."""
    
    def __init__(self):
        """Initialize BuoyService."""
        self.base_url = settings.ndbc_base_url
        
    async def get_realtime_observations(self, station_id: str) -> Dict[str, Any]:
        """Fetch real-time observations from NDBC for a specific station."""
        try:
            url = f"{self.base_url}/{station_id}.txt"
            ssl_context = None  # Let aiohttp handle SSL verification
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10, ssl=ssl_context) as response:
                    response.raise_for_status()
                    text = await response.text()

            lines = text.strip().split('\n')
            data = None

            # Skip header lines and get first data line
            for line in lines:
                if not line.startswith('#'):
                    data = line.split()
                    break
            
            if not data:
                logger.error("Failed to parse data")
                raise ValueError("Invalid data format from NDBC")
            
            # Create observation with fixed field positions
            observation = {}
            
            # Create timestamp using fixed positions (NDBC format is standardized)
            try:
                if len(data) >= 5:  # Ensure we have enough fields
                    observation_time = datetime(
                        year=int(data[0]),
                        month=int(data[1]),
                        day=int(data[2]),
                        hour=int(data[3]) if data[3] != "MM" else 0,
                        minute=int(data[4]) if data[4] != "MM" else 0,
                        tzinfo=timezone.utc
                    )
                    observation['timestamp'] = observation_time
                    
                    # Calculate how out of date the reading is
                    current_time = datetime.now(timezone.utc)
                    time_diff = current_time - observation_time
                    minutes_old = time_diff.total_seconds() / 60
                    
                    # Add freshness information
                    observation['data_age'] = {
                        'minutes': round(minutes_old, 1),
                        'is_stale': minutes_old > 45  # Consider data stale if more than 45 minutes old
                    }
                else:
                    raise ValueError("Not enough fields for timestamp")
            except (ValueError, IndexError) as e:
                logger.error(f"Error creating timestamp: {str(e)}")
                raise ValueError(f"Invalid timestamp data: {str(e)}")

            if len(data) >= 19:  # Check if we have all possible fields
                field_positions = {
                    5: 'wind_dir',      # WDIR
                    6: 'wind_speed',    # WSPD
                    7: 'wind_gust',     # GST
                    8: 'wave_height',   # WVHT
                    9: 'dominant_period', # DPD
                    10: 'average_period', # APD
                    11: 'mean_wave_direction', # MWD
                    12: 'pressure',     # PRES
                    13: 'air_temp',     # ATMP
                    14: 'water_temp',   # WTMP
                    15: 'dewpoint',     # DEWP
                    16: 'visibility',   # VIS
                    17: 'pressure_tendency', # PTDY
                    18: 'tide'         # TIDE
                }
                
                # Process each field
                for pos, field_name in field_positions.items():
                    if pos < len(data):
                        value = data[pos]
                        if value == "MM":
                            observation[field_name] = None
                        else:
                            try:
                                observation[field_name] = float(value)
                            except ValueError:
                                observation[field_name] = None
                                logger.warning(f"Could not convert {field_name} value '{value}' to float")
                    else:
                        observation[field_name] = None
            
            return observation
            
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching data for station {station_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing data for station {station_id}: {str(e)}")
            raise