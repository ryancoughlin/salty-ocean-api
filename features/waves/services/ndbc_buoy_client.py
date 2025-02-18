import logging
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Union, Dict
from fastapi import HTTPException

from features.waves.models.ndbc_types import (
    NDBCWindData,
    NDBCWaveData,
    NDBCMetData,
    NDBCDataAge,
    NDBCObservation,
    NDBCStation
)
from core.config import settings

logger = logging.getLogger(__name__)

class NDBCBuoyClient:
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

    def _parse_value(self, value: str) -> Optional[float]:
        """Parse NDBC value, handling missing value indicators."""
        if value in ['MM', 'missing']:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def get_observation(self, station_id: str, station_info: Dict) -> Optional[NDBCStation]:
        """Get latest observation data for a station."""
        try:
            session = await self._init_session()
            
            # Construct URL for standard meteorological data
            url = f"{settings.ndbc_base_url}{station_id}.{settings.ndbc_data_types['std']}"
            
            async with session.get(
                url,
                timeout=30,
                verify_ssl=False  # Disable SSL verification
            ) as response:
                response.raise_for_status()
                text = await response.text()
                
                if not text:
                    return None
                    
                # Parse the text data (NDBC standard format)
                lines = text.strip().split('\n')
                if len(lines) < 2:  # Need at least header and one data line
                    return None
                    
                # Get latest observation (first data line after header)
                headers = lines[0].strip().split()
                data = lines[2].strip().split()  # Skip units line
                data_dict = dict(zip(headers, data))
                
                # Parse time
                obs_time = datetime.strptime(
                    f"{data_dict['#YY']}-{data_dict['MM']}-{data_dict['DD']} {data_dict['hh']}:{data_dict['mm']}",
                    "%Y-%m-%d %H:%M"
                )
                obs_time = obs_time.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - obs_time).total_seconds() / 60
                
                observation = NDBCObservation(
                    time=obs_time,
                    wind=NDBCWindData(
                        speed=self._parse_value(data_dict.get('WSPD')),
                        direction=self._parse_value(data_dict.get('WDIR')),
                        gust=self._parse_value(data_dict.get('GST'))
                    ),
                    wave=NDBCWaveData(
                        height=self._parse_value(data_dict.get('WVHT')),
                        period=self._parse_value(data_dict.get('DPD')),
                        direction=self._parse_value(data_dict.get('MWD')),
                        average_period=self._parse_value(data_dict.get('APD')),
                        steepness=data_dict.get('STEEPNESS', '')
                    ),
                    met=NDBCMetData(
                        pressure=self._parse_value(data_dict.get('PRES')),
                        air_temp=self._parse_value(data_dict.get('ATMP')),
                        water_temp=self._parse_value(data_dict.get('WTMP')),
                        dewpoint=self._parse_value(data_dict.get('DEWP')),
                        visibility=self._parse_value(data_dict.get('VIS')),
                        pressure_tendency=self._parse_value(data_dict.get('PTDY')),
                        water_level=self._parse_value(data_dict.get('TIDE'))
                    ),
                    data_age=NDBCDataAge(
                        minutes=age_minutes,
                        isStale=age_minutes > 45
                    )
                )

                return NDBCStation(
                    station_id=station_id,
                    name=station_info["name"],
                    location={
                        "type": "Point",
                        "coordinates": station_info["location"]["coordinates"]
                    },
                    observations=observation
                )
                
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching observation for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail=f"Error fetching observation data: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error processing observation for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing observation data: {str(e)}"
            ) 