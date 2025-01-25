import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional

from services.prefetch_service import PrefetchService
from core.config import settings

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing scheduled data prefetch tasks."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.prefetch_service = PrefetchService()
        
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            
            # Schedule wave model updates (6 hours after model run times to ensure data is ready)
            # Run at 6:30, 12:30, 18:30, and 00:30 UTC
            self.scheduler.add_job(
                self.prefetch_service.prefetch_wave_forecasts,
                CronTrigger(hour="0,6,12,18", minute="30"),
                id="wave_forecasts",
                name="Wave Model Update",
                misfire_grace_time=3600  # Allow up to 1 hour delay if system is busy
            )
    
            # Initial prefetch with delay to avoid immediate load
            self.scheduler.add_job(
                self.prefetch_service.prefetch_all,
                'date',
                run_date=datetime.now() + timedelta(minutes=2),  # Start after 2 minutes
                id="initial_prefetch",
                name="Initial Data Prefetch"
            )
            
            self.scheduler.start()
            logger.info("Scheduler started successfully")
        else:
            logger.warning("Scheduler is already running")
            
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
        else:
            logger.warning("Scheduler is not running")
            
    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """Get the next scheduled run time for a job."""
        job = self.scheduler.get_job(job_id)
        return job.next_run_time if job else None 