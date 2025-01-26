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
            # Schedule wave model updates to run 30 minutes after each model run time
            # GFS-Wave model runs are available at approximately 00Z, 06Z, 12Z, and 18Z
            # We schedule 30 minutes after to ensure data is available
            for hour in [0, 6, 12, 18]:
                job_id = f"wave_forecasts_{hour:02d}z"
                self.scheduler.add_job(
                    self.prefetch_service.prefetch_wave_forecasts,
                    CronTrigger(hour=str(hour), minute="30"),
                    id=job_id,
                    name=f"Wave Model Update {hour:02d}Z",
                    misfire_grace_time=3600,  # Allow up to 1 hour delay
                    coalesce=True  # Only run once if multiple executions are missed
                )
                logger.info(f"Scheduled {job_id} to run at {hour:02d}:30 UTC")
            
            # Add a backup job that runs every 4 hours offset from main runs
            # This helps catch any missed updates
            self.scheduler.add_job(
                self.prefetch_service.prefetch_wave_forecasts,
                CronTrigger(hour="2,8,14,20", minute="30"),
                id="wave_forecasts_backup",
                name="Wave Model Backup Update",
                misfire_grace_time=3600,
                coalesce=True
            )
    
            # Initial prefetch with short delay to avoid immediate load
            self.scheduler.add_job(
                self.prefetch_service.prefetch_all,
                'date',
                run_date=datetime.now() + timedelta(seconds=30),  # Start after 30 seconds
                id="initial_prefetch",
                name="Initial Data Prefetch"
            )
            
            self.scheduler.start()
            logger.info("Scheduler started successfully")
            
            # Log next run times for all jobs
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                logger.info(f"Next run for {job.name}: {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')}")
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