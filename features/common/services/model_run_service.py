import asyncio
import logging
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Tuple
from email.utils import parsedate_to_datetime
from pydantic import BaseModel, validator

import aiohttp

logger = logging.getLogger(__name__)

class ModelRun(BaseModel):
    """Model run information with availability details."""
    run_date: date
    cycle_hour: int
    available_time: datetime
    delay_minutes: Optional[int] = None

    @validator('delay_minutes', always=True)
    def compute_delay(cls, v, values):
        if 'available_time' in values and 'run_date' in values and 'cycle_hour' in values:
            # Create timezone-aware datetime for the scheduled time
            scheduled_dt = datetime.combine(
                values['run_date'],
                time(hour=values['cycle_hour'])
            ).replace(tzinfo=timezone.utc)
            
            # available_time is already UTC from parsedate_to_datetime
            delay = (values['available_time'] - scheduled_dt).total_seconds() / 60.0
            return int(delay)
        return v

    def __str__(self):
        return (f"ModelRun(run_date={self.run_date}, cycle_hour={self.cycle_hour}Z, "
                f"available_time={self.available_time}, delay_minutes={self.delay_minutes})")

class ModelRunService:
    """Service to check for available GFS model runs."""
    
    def __init__(self):
        self.current_cycle: Optional[ModelRun] = None
        
    def _print_model_run_info(self, model_run: ModelRun, check_date: date, cycle: int):
        """Print model run information with both UTC and EST times."""
        utc_time = model_run.available_time
        est_time = utc_time.astimezone(timezone(timedelta(hours=-5)))
        print(f"\n✨ Using GFS model run: {check_date.strftime('%Y%m%d')} {cycle:02d}Z")
        print(f"⏰ Available since: {utc_time.strftime('%H:%M:%S')} UTC ({est_time.strftime('%H:%M:%S')} EST)")
        print(f"⌛ Delay: {model_run.delay_minutes} minutes\n")

    async def check_grib_file_for_cycle(
        self,
        target_date: date,
        cycle_hour: int,
        min_size: int = 100
    ) -> Optional[ModelRun]:
        """Check if a specific model cycle is available."""
        date_str = target_date.strftime("%Y%m%d")
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
        # Ensure we're working with UTC time
        now = datetime.now(timezone.utc)
        target_date = now.date()
        cycles = [0, 6, 12, 18]
        
        # Check today and yesterday only - no need to go back further
        for delta in [0, -1]:
            check_date = target_date + timedelta(days=delta)
            
            # Check cycles in reverse order (latest first)
            # But only check cycles that should be ready based on current time
            current_hour = now.hour
            available_cycles = [c for c in cycles if c <= current_hour - 3 or delta < 0]
            
            for cycle in sorted(available_cycles, reverse=True):
                model_run = await self.check_grib_file_for_cycle(check_date, cycle)
                if model_run:
                    # Only print info if this is a new cycle or first run
                    if not self.current_cycle or (
                        model_run.run_date != self.current_cycle.run_date or 
                        model_run.cycle_hour != self.current_cycle.cycle_hour
                    ):
                        self._print_model_run_info(model_run, check_date, cycle)
                    self.current_cycle = model_run
                    return model_run
        
        # If we get here, use yesterday's last successful cycle
        yesterday = target_date - timedelta(days=1)
        last_cycle = max(c for c in cycles if c <= current_hour)
        logger.warning(f"No recent cycles found, falling back to yesterday's {last_cycle:02d}Z cycle")
        return ModelRun(
            run_date=yesterday,
            cycle_hour=last_cycle,
            available_time=datetime.now(timezone.utc)
        )

    def get_current_cycle(self) -> Optional[ModelRun]:
        """Get the currently loaded model run."""
        return self.current_cycle 