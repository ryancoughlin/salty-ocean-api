import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta

from services.prefetch_service import PrefetchService
from core.config import settings

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.prefetch_service = PrefetchService()
        
    def start(self):
        """Start the scheduler with configured jobs."""
        logger.info("Starting scheduler")
        
        # Schedule wave forecast prefetch every 6 hours
        self.scheduler.add_job(
            self.prefetch_service.prefetch_wave_forecasts,
            IntervalTrigger(hours=6),
            name='wave_forecasts',
            next_run_time=datetime.now()
        )
        
        self.scheduler.start()
        logger.info("Scheduler started successfully")
        
    def get_next_run_time(self, job_id: str) -> str:
        """Get the next run time for a scheduled job."""
        job = self.scheduler.get_job(job_id)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None
        
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            logger.info("Shutting down scheduler")
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown complete") 