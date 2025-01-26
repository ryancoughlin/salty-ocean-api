import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional
from pathlib import Path

from services.wave_data_processor import WaveDataProcessor
from repositories.station_repo import StationRepository
from controllers.offshore_controller import OffshoreController

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing scheduled data prefetch tasks."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.wave_processor = WaveDataProcessor()
        
    async def _update_model_data(self):
        """Update model data by loading new GRIB files."""
        try:
            logger.info("Starting model data update")
            await self.wave_processor.preload_dataset()
            logger.info("Completed model data update")
        except Exception as e:
            logger.error(f"Error updating model data: {str(e)}")
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            # Schedule updates 5.5 hours after each model run
            for hour in [0, 6, 12, 18]:
                run_hour = (hour + 5) % 24  # 5.5 hours after model run
                job_id = f"wave_forecasts_{hour:02d}z"
                self.scheduler.add_job(
                    self._update_model_data,
                    CronTrigger(hour=str(run_hour), minute="30"),
                    id=job_id,
                    name=f"Wave Model Update {hour:02d}Z",
                    misfire_grace_time=3600,  # Allow up to 1 hour delay
                    coalesce=True  # Only run once if multiple executions are missed
                )
                logger.info(f"Scheduled {job_id} to run at {run_hour:02d}:30 UTC")
            
            self.scheduler.start()
            logger.info("Scheduler started successfully")
            
            # Log next run times
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