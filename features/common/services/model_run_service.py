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
        logger.info(f"📊 Model Run: {model_run.date_str} {cycle:02d}Z")
        logger.info(f"   ├─ Available: {model_run.available_time.strftime('%H:%M:%S')} UTC ({model_run.local_time.strftime('%H:%M:%S')} EST)")
        logger.info(f"   └─ Expected: {model_run.expected_available_time.strftime('%H:%M:%S')} UTC")

    @staticmethod
    def is_newer_run(new_run: ModelRun, current_run: ModelRun) -> bool:
        """Check if a model run is newer than the current one.
        
        Args:
            new_run: The potentially newer model run
            current_run: The current model run
            
        Returns:
            bool: True if new_run is newer than current_run
        """
        if not new_run or not current_run:
            return False
            
        # Compare dates first
        if new_run.run_date > current_run.run_date:
            return True
        elif new_run.run_date < current_run.run_date:
            return False
            
        # Same date, compare cycle hours
        return new_run.cycle_hour > current_run.cycle_hour

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
                # Use proper ClientTimeout object
                timeout = aiohttp.ClientTimeout(total=30)
                async with session.head(url, timeout=timeout) as response:
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
                    if not hasattr(self, '_last_model_run') or self.is_newer_run(model_run, self._last_model_run):
                        self._log_model_run_info(model_run, check_date, cycle)
                        self._last_model_run = model_run
                    return model_run
        
        # If we get here, use yesterday's last successful cycle
        yesterday = target_date - timedelta(days=1)
        last_cycle = 18  # Default to last cycle of the day
        logger.warning("⚠️  No recent cycles found, falling back to yesterday's 18Z cycle")
        return ModelRun(
            run_date=yesterday,
            cycle_hour=last_cycle,
            available_time=datetime.now(timezone.utc)
        ) 