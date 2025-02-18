from datetime import datetime, time, timedelta, timezone
from typing import Dict, Optional, Tuple
import logging
import aiohttp

from features.common.models.model_run_types import (
    CycleStatus,
    CycleAttempt,
    ModelRunConfig,
    ModelRunMetrics
)
from features.common.exceptions.model_run_exceptions import (
    CycleNotAvailableError,
    CycleDownloadError
)
from core.config import settings

logger = logging.getLogger(__name__)

class ModelRunService:
    """Service for managing GFS model run calculations and status.
    
    The GFS (Global Forecast System) runs 4 times daily at:
    - 00Z
    - 06Z
    - 12Z
    - 18Z
    
    Each cycle's availability is checked dynamically by verifying
    the existence of required files on NOAA's servers.
    """
    
    def __init__(self, config: Optional[ModelRunConfig] = None) -> None:
        """Initialize the model run service.
        
        Args:
            config: Optional configuration for the service
        """
        self.config = config or ModelRunConfig()
        self.metrics = ModelRunMetrics()
        self._cycle_attempts: Dict[str, CycleAttempt] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_cycle: Optional[Tuple[datetime, str]] = None
    
    async def _init_session(self) -> aiohttp.ClientSession:
        """Initialize or return existing HTTP session."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    def _calculate_current_cycle(self) -> tuple[datetime, str]:
        """Calculate the current GFS cycle based on time.
        
        The GFS runs every 6 hours at 00Z, 06Z, 12Z, and 18Z.
        Files are typically available 4 hours after the cycle starts.
        So we look back one cycle to ensure we have data.
        
        Returns:
            tuple[datetime, str]: (cycle_date, cycle_hour)
        """
        current_time = datetime.now(timezone.utc)
        
        # Calculate current cycle hour (00, 06, 12, 18)
        cycle_hour = (current_time.hour // 6) * 6
        
        # Look back one cycle to ensure data is ready
        cycle_hour -= 6
        cycle_date = current_time.date()
        
        # Handle previous day if needed
        if cycle_hour < 0:
            cycle_hour = 18
            cycle_date -= timedelta(days=1)
            
        return cycle_date, f"{cycle_hour:02d}"
    
    async def get_latest_available_cycle(self) -> tuple[datetime, str]:
        """Get the latest GFS cycle that should have data available.
        
        Returns:
            tuple[datetime, str]: (cycle_date, cycle_hour)
        """
        if self._current_cycle:
            return self._current_cycle
            
        # Calculate cycle based on current time
        cycle_date, cycle_hour = self._calculate_current_cycle()
        logger.info(f"Using GFS cycle: {cycle_date.strftime('%Y%m%d')} {cycle_hour}Z")
        
        self._current_cycle = (cycle_date, cycle_hour)
        return self._current_cycle
    
    def track_attempt(self, 
                     cycle_date: datetime,
                     cycle_hour: str,
                     status: CycleStatus,
                     error: Optional[str] = None) -> None:
        """Track an attempt to download a cycle.
        
        Args:
            cycle_date: Date of the cycle
            cycle_hour: Hour of the cycle (00, 06, 12, 18)
            status: Status of the attempt
            error: Optional error message
        """
        cycle_id = f"{cycle_date.strftime('%Y%m%d')}_{cycle_hour}"
        attempt = self._cycle_attempts.get(cycle_id)
        
        if attempt is None:
            attempt = CycleAttempt(cycle_id=cycle_id)
            self._cycle_attempts[cycle_id] = attempt
        
        attempt.attempts += 1
        attempt.last_attempt = datetime.now(timezone.utc)
        attempt.status = status
        attempt.error = error
        
        # Update metrics
        self.metrics.total_attempts += 1
        if status == CycleStatus.COMPLETE:
            self.metrics.successful_attempts += 1
            self.metrics.last_successful_cycle = cycle_id
        elif status == CycleStatus.FAILED:
            self.metrics.failed_attempts += 1
            
        logger.info(
            f"Cycle {cycle_id} attempt {attempt.attempts}: {status.value}"
            + (f" - {error}" if error else "")
        )
    
    def should_retry(self, cycle_date: datetime, cycle_hour: str) -> bool:
        """Determine if we should retry downloading a cycle.
        
        Args:
            cycle_date: Date of the cycle
            cycle_hour: Hour of the cycle (00, 06, 12, 18)
            
        Returns:
            bool indicating if we should retry
        """
        cycle_id = f"{cycle_date.strftime('%Y%m%d')}_{cycle_hour}"
        attempt = self._cycle_attempts.get(cycle_id)
        
        if not attempt:
            return True
        
        # Check max attempts
        if attempt.attempts >= self.config.max_attempts:
            logger.warning(
                f"Cycle {cycle_id} has reached max attempts ({self.config.max_attempts})"
            )
            return False
        
        # Check if enough time has passed since last attempt
        time_since_last = datetime.now(timezone.utc) - attempt.last_attempt
        required_delay = timedelta(
            minutes=self.config.min_retry_delay_minutes * (2 ** (attempt.attempts - 1))
        )
        
        return time_since_last >= required_delay
    
    def get_cycle_status(self, cycle_date: datetime, cycle_hour: str) -> CycleStatus:
        """Get the status of a cycle.
        
        Args:
            cycle_date: Date of the cycle
            cycle_hour: Hour of the cycle (00, 06, 12, 18)
            
        Returns:
            CycleStatus indicating current status
        """
        cycle_id = f"{cycle_date.strftime('%Y%m%d')}_{cycle_hour}"
        attempt = self._cycle_attempts.get(cycle_id)
        return attempt.status if attempt else CycleStatus.PENDING
    
    def get_metrics(self) -> ModelRunMetrics:
        """Get current metrics.
        
        Returns:
            Current metrics for the service
        """
        return self.metrics 