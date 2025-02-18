from datetime import datetime, timezone
import logging
from typing import Optional
import aiohttp

from core.config import settings
from features.common.models.model_run_types import ModelRunStatus, ModelRunAttempt, ModelRunConfig
from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.wind.services.gfs_wind_client import GFSWindClient

logger = logging.getLogger(__name__)

async def check_wave_bulletin_availability(
    session: aiohttp.ClientSession,
    date: str,
    hour: str,
    station_id: str
) -> bool:
    """Check if wave bulletin file is available for a given cycle and station."""
    url = (f"{settings.gfs_wave_base_url}/gfs.{date}/{hour}/wave/station/"
           f"bulls.t{hour}z/gfswave.{station_id}.bull")
    
    try:
        async with session.head(url) as response:
            return response.status == 200
    except Exception as e:
        logger.error(f"Error checking wave bulletin: {str(e)}")
        return False

async def check_wind_grib_availability(
    session: aiohttp.ClientSession,
    date: str,
    hour: str
) -> bool:
    """Check if wind GRIB file is available for a given cycle."""
    url = (f"{settings.gfs_wave_base_url}/gfs.{date}/{hour}/atmos/"
           f"gfs.t{hour}z.pgrb2.0p25.f000")
    
    try:
        async with session.head(url) as response:
            return response.status == 200
    except Exception as e:
        logger.error(f"Error checking wind GRIB: {str(e)}")
        return False

async def verify_cycle_availability(
    session: aiohttp.ClientSession,
    date: str,
    hour: str,
    test_station_id: str
) -> bool:
    """Verify availability of all required files for a cycle."""
    is_wave_available = await check_wave_bulletin_availability(
        session, date, hour, test_station_id
    )
    is_wind_available = await check_wind_grib_availability(session, date, hour)
    
    return is_wave_available and is_wind_available

async def process_model_cycle(
    wave_client: NOAAGFSClient,
    wind_client: GFSWindClient,
    cycle_date: datetime,
    cycle_hour: str,
    config: ModelRunConfig
) -> ModelRunAttempt:
    """Process a model cycle and return the attempt result."""
    date_str = cycle_date.strftime("%Y%m%d")
    cycle_id = f"{date_str}_{cycle_hour}"
    
    try:
        # Verify data availability
        async with aiohttp.ClientSession() as session:
            is_available = await verify_cycle_availability(
                session, date_str, cycle_hour, config.test_station_id
            )
            if not is_available:
                return ModelRunAttempt(
                    cycle_id=cycle_id,
                    status=ModelRunStatus.PENDING,
                    error="Cycle files not yet available"
                )

        # Download and validate wave data
        bulletin = await wave_client._get_station_bulletin(
            config.test_station_id, date_str, cycle_hour
        )
        if not bulletin:
            return ModelRunAttempt(
                cycle_id=cycle_id,
                status=ModelRunStatus.FAILED,
                error="Failed to download wave bulletin"
            )

        # Download and validate wind data
        test_lat, test_lon = config.test_location
        test_url = wind_client._build_grib_filter_url(
            cycle_date, cycle_hour, 0, test_lat, test_lon
        )
        grib_file = await wind_client._get_grib_file(
            test_url, "test", cycle_date, cycle_hour, 0
        )
        if not grib_file:
            return ModelRunAttempt(
                cycle_id=cycle_id,
                status=ModelRunStatus.FAILED,
                error="Failed to download wind data"
            )

        return ModelRunAttempt(
            cycle_id=cycle_id,
            status=ModelRunStatus.COMPLETE
        )

    except Exception as e:
        logger.error(f"Error processing cycle {cycle_id}: {str(e)}")
        return ModelRunAttempt(
            cycle_id=cycle_id,
            status=ModelRunStatus.FAILED,
            error=str(e)
        ) 