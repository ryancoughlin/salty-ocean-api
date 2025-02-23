import logging
from datetime import datetime, date, time, timezone
from typing import Optional, Tuple, ClassVar, List
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class ModelRun(BaseModel):
    """Model run information with availability details."""
    run_date: date
    cycle_hour: int
    available_time: datetime
    delay_minutes: Optional[int] = None

    # Constants
    VALID_CYCLES: ClassVar[List[int]] = [0, 6, 12, 18]
    PROCESSING_DELAY_HOURS: ClassVar[int] = 4

    @staticmethod
    def get_current_time() -> Tuple[datetime, datetime]:
        """Get current time in both UTC and local time."""
        utc_now = datetime.now(timezone.utc)
        local_now = datetime.now()
        return utc_now, local_now

    @staticmethod
    def get_available_cycles(current_hour: int, check_previous_day: bool = False) -> list[int]:
        """Get list of cycles that should be available based on current hour."""
        return [
            c for c in ModelRun.VALID_CYCLES 
            if (c + ModelRun.PROCESSING_DELAY_HOURS <= current_hour) or check_previous_day
        ]

    @validator('run_date')
    def validate_run_date(cls, v):
        """Ensure run_date is not in the future."""
        utc_now, _ = cls.get_current_time()
        if v > utc_now.date():
            raise ValueError(f"Run date {v} is in the future")
        return v

    @validator('cycle_hour')
    def validate_cycle_hour(cls, v):
        """Ensure cycle_hour is valid."""
        if v not in cls.VALID_CYCLES:
            raise ValueError(f"Invalid cycle hour {v}. Must be one of {cls.VALID_CYCLES}")
        return v

    @validator('available_time')
    def ensure_utc(cls, v):
        """Ensure available_time is always in UTC."""
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def local_date(self) -> date:
        """Get the run date in local time."""
        utc_dt = datetime.combine(self.run_date, time(self.cycle_hour)).replace(tzinfo=timezone.utc)
        local_dt = utc_dt.astimezone()  # Convert to system's local timezone
        return local_dt.date()

    @property
    def date_str(self) -> str:
        """Get the local date string in YYYYMMDD format."""
        return self.local_date.strftime('%Y%m%d')

    @property
    def local_time(self) -> datetime:
        """Get the available time in local time zone."""
        return self.available_time.astimezone()  # Convert to system's local timezone

    @validator('delay_minutes', always=True)
    def compute_delay(cls, v, values):
        if 'available_time' in values and 'run_date' in values and 'cycle_hour' in values:
            # Create timezone-aware datetime for the scheduled time
            scheduled_dt = datetime.combine(
                values['run_date'],
                time(hour=values['cycle_hour'])
            ).replace(tzinfo=timezone.utc)
            
            # Calculate delay using UTC times
            delay = (values['available_time'] - scheduled_dt).total_seconds() / 60.0
            return int(delay)
        return v

    def __str__(self):
        return (f"ModelRun(run_date={self.local_date}, cycle_hour={self.cycle_hour}Z, "
                f"available_time={self.local_time}, delay_minutes={self.delay_minutes})")