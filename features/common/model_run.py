import logging
from datetime import datetime, date, time, timezone
from typing import Optional
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