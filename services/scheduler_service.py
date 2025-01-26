import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from core.config import settings

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduling model data updates."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.wave_processor = WaveDataProcessor()
        self.wave_downloader = WaveDataDownloader()
        
    async def _update_model_data(self):
        """Download and process new model data."""
        try:
            logger.info("Downloading new model data")
            success = await self.wave_downloader.download_model_data()
            if success:
                logger.info("Successfully downloaded new model data")
            else:
                logger.warning("Failed to download model data")
        except Exception as e:
            logger.error(f"Error updating model data: {str(e)}")
    
    def start(self):
        """Start the scheduler."""
        if self.scheduler.running:
            return
            
        # Schedule updates at NOAA model run times: 00, 06, 12, 18 UTC
        for model_run in settings.model_runs:
            self.scheduler.add_job(
                self._update_model_data,
                CronTrigger(hour=model_run),  # Run at model run times
                id=f"wave_forecasts_{model_run}z",
                name=f"Wave Model Update {model_run}Z",
                misfire_grace_time=3600,
                coalesce=True
            )
            logger.info(f"Scheduled update for {model_run}z run")
            
        self.scheduler.start()
        logger.info("Scheduler started")
            
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            
    def get_next_run_time(self, job_id: str):
        """Get next scheduled run time."""
        job = self.scheduler.get_job(job_id)
        return job.next_run_time if job else None 