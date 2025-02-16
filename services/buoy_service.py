import aiohttp
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional, List
from core.config import settings
import pandas as pd
from models.buoy import NDBCObservation, WindData, WaveData

logger = logging.getLogger(__name__)

class BuoyService:
    """Service for interacting with NDBC buoy data."""
    
    def __init__(self):
        """Initialize BuoyService."""
        self.base_url = settings.ndbc_base_url
        
    async def get_realtime_observations(self, station_id: str) -> Optional[NDBCObservation]:
        """Get latest observations for a station."""
        try:
            url = f"https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching data for station {station_id}: {response.status}")
                        return None
                        
                    text = await response.text()
                    
            # Parse the text data
            try:
                df = pd.read_csv(
                    pd.StringIO(text),
                    delim_whitespace=True,
                    header=0,
                    na_values=['MM']
                )
                
                if df.empty:
                    return None
                    
                # Get latest row
                latest = df.iloc[0]
                
                # Convert to datetime
                time = pd.to_datetime(
                    f"{latest['#YY']}-{latest['MM']}-{latest['DD']} {latest['hh']}:00",
                    format="%Y-%m-%d %H:%M"
                )
                
                # Extract wave data
                wave = WaveData(
                    height=latest.get('WVHT', None),
                    period=latest.get('DPD', None),
                    direction=latest.get('MWD', None),
                    wind_height=latest.get('WWH', None),
                    wind_period=latest.get('WWP', None),
                    wind_direction=latest.get('WWD', None)
                )
                
                # Extract wind data
                wind = WindData(
                    speed=latest.get('WSPD', None),
                    direction=latest.get('WDIR', None)
                )
                
                return NDBCObservation(
                    time=time,
                    wave=wave,
                    wind=wind
                )
                
            except Exception as e:
                logger.error(f"Error parsing data for station {station_id}: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching data for station {station_id}: {str(e)}")
            return None