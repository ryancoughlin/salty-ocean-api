import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Tuple
from email.utils import parsedate_to_datetime
from features.common.model_run import ModelRun

import aiohttp

logger = logging.getLogger(__name__)

class ModelRunService:
    """Service to check for available GFS model runs."""
    
    def _log_model_run_info(self, model_run: ModelRun, check_date: date, cycle: int):
        """Log model run information with both UTC and EST times."""
        logger.info(f"✨ Using GFS model run: {model_run.date_str} {cycle:02d}Z")
        logger.info(f"⏰ Available since: {model_run.available_time.strftime('%H:%M:%S')} UTC "
                   f"({model_run.local_time.strftime('%H:%M:%S')} EST)")
        logger.info(f"⌛ Delay: {model_run.delay_minutes} minutes")

    async def check_grib_file_for_cycle(
        self,
        target_date: date,
        cycle_hour: int,
        min_size: int = 100
    ) -> Optional[ModelRun]:
        """Check if a specific model cycle is available."""
        # Create temporary model run to get correct date string
        temp_model = ModelRun(
            run_date=target_date,
            cycle_hour=cycle_hour,
            available_time=datetime.now(timezone.utc)
        )
        date_str = temp_model.date_str
        cycle_str = f"{cycle_hour:02d}"
        
        # Check for the first GRIB file directly
        url = f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.{date_str}/{cycle_str}/wave/gridded/gfswave.t{cycle_str}z.atlocn.0p16.f000.grib2"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=30) as response:
                    if response.status != 200:
                        return None
                        
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) < min_size:
                        return None
                        
                    last_modified = response.headers.get("Last-Modified")
                    if not last_modified:
                        return None
                        
                    # parsedate_to_datetime returns UTC time
                    available_time = parsedate_to_datetime(last_modified)
                    model_run = ModelRun(
                        run_date=target_date,
                        cycle_hour=cycle_hour,
                        available_time=available_time
                    )
                    return model_run
                    
        except Exception as e:
            logger.error(f"Error checking cycle {cycle_str}Z: {e}")
            return None

    async def get_latest_available_cycle(self) -> Optional[ModelRun]:
        """Get the latest available model cycle."""
        # Get current time in both UTC and EST
        utc_now, est_now = ModelRun.get_current_time()
        logger.info(f"Current time: {est_now.strftime('%Y-%m-%d %H:%M:%S')} EST")
        
        target_date = utc_now.date()
        
        # Check today and yesterday only - no need to go back further
        for delta in [0, -1]:
            check_date = target_date + timedelta(days=delta)
            check_previous = delta < 0
            
            # Get available cycles based on current hour
            available_cycles = ModelRun.get_available_cycles(utc_now.hour, check_previous)
            logger.debug(f"Checking date {check_date} for cycles: {available_cycles}")
            
            for cycle in sorted(available_cycles, reverse=True):
                model_run = await self.check_grib_file_for_cycle(check_date, cycle)
                if model_run:
                    # Only log model run info during startup or when a new run is detected
                    if not hasattr(self, '_last_model_run') or (
                        self._last_model_run.run_date != model_run.run_date or 
                        self._last_model_run.cycle_hour != model_run.cycle_hour
                    ):
                        self._log_model_run_info(model_run, check_date, cycle)
                        self._last_model_run = model_run
                    return model_run
        
        # If we get here, use yesterday's last successful cycle
        yesterday = target_date - timedelta(days=1)
        last_cycle = 18  # Default to last cycle of the day
        logger.warning(f"No recent cycles found, falling back to yesterday's {last_cycle:02d}Z cycle")
        return ModelRun(
            run_date=yesterday,
            cycle_hour=last_cycle,
            available_time=datetime.now(timezone.utc)
        ) 