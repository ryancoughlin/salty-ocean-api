import logging
import aiohttp
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException

from features.stations.models.station_types import (
    NDBCWindData,
    NDBCWaveData,
    NDBCMetData,
    NDBCDataAge,
    NDBCObservation
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

    async def get_observation(self, station_id: str) -> Optional[NDBCObservation]:
        """Get latest observation data for a station."""
        try:
            session = await self._init_session()
            
            params = {
                "station": station_id,
                "time_zone": "0",  # UTC
                "units": "metric",
                "format": "json"
            }
            
            async with session.get(
                settings.ndbc_realtime_url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=30,
                verify_ssl=False  # Disable SSL verification
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not data:
                    return None
                    
                # Get latest observation
                latest = data[0]
                
                # Calculate data age
                obs_time = datetime.strptime(latest["time"], "%Y-%m-%d %H:%M:%S")
                obs_time = obs_time.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - obs_time).total_seconds() / 60
                
                return NDBCObservation(
                    time=obs_time,
                    wind=NDBCWindData(
                        speed=latest.get("wspd"),
                        direction=latest.get("wdir"),
                        gust=latest.get("gst")
                    ),
                    wave=NDBCWaveData(
                        height=latest.get("wvht"),
                        period=latest.get("dpd"),
                        direction=latest.get("mwd"),
                        average_period=latest.get("apd"),
                        steepness=latest.get("steepness")
                    ),
                    met=NDBCMetData(
                        pressure=latest.get("pres"),
                        air_temp=latest.get("atmp"),
                        water_temp=latest.get("wtmp"),
                        dewpoint=latest.get("dewp"),
                        visibility=latest.get("vis"),
                        pressure_tendency=latest.get("ptdy"),
                        water_level=latest.get("tide")
                    ),
                    data_age=NDBCDataAge(
                        minutes=age_minutes,
                        isStale=age_minutes > 45
                    )
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