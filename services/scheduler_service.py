import logging
import asyncio
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job

from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from services.prefetch_service import PrefetchService
from fastapi_cache import FastAPICache

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduling wave model data updates."""
    
    RUN_HOURS = [0, 6, 12, 18]  # Model run hours (UTC)
    UPDATE_DELAY = 30  # Minutes after the hour to check for updates
    
    def __init__(
        self,
        wave_processor: WaveDataProcessor,
        wave_downloader: WaveDataDownloader,
        prefetch_service: PrefetchService
    ):
        self.scheduler = AsyncIOScheduler()
        self.wave_processor = wave_processor
        self.wave_downloader = wave_downloader
        self.prefetch_service = prefetch_service
        
    async def _update_model_data(self, run_hour: int) -> None:
        """Update wave model data for a specific run hour."""
        try:
            logger.debug(f"Checking for {run_hour:02d}z model run updates...")
            
            if not await self.wave_downloader.download_latest():
                logger.debug(f"No updates needed for {run_hour:02d}z run")
                return
                
            logger.info("New model data available - flushing cache")
            await FastAPICache.clear()
            
            if not await self.wave_processor.preload_dataset():
                logger.error("Failed to load new model data")
                return
                
            await self.prefetch_service.prefetch_all()
            logger.info(f"Successfully updated {run_hour:02d}z model data")
                
        except Exception as e:
            logger.error(f"Error during {run_hour:02d}z model update: {str(e)}")
            
    def _schedule_job(self, run_hour: int) -> None:
        """Schedule a single update job for the given run hour."""
        job_id = f"model_update_{run_hour}z"
        self.scheduler.add_job(
            self._update_model_data,
            CronTrigger(hour=run_hour, minute=self.UPDATE_DELAY),
            args=[run_hour],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled update for {run_hour:02d}z run at {run_hour:02d}:{self.UPDATE_DELAY:02d} UTC")

    async def start(self) -> None:
        """Start the scheduler and schedule all update jobs."""
        try:
            for run_hour in self.RUN_HOURS:
                self._schedule_job(run_hour)
                
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("Scheduler started successfully")
                
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            raise
            
    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            
    def get_next_run_time(self, run_hour: int) -> Optional[str]:
        """Get the next scheduled run time for a specific model run hour."""
        if run_hour not in self.RUN_HOURS:
            return None
            
        job_id = f"model_update_{run_hour}z"
        job = self.scheduler.get_job(job_id)
        return job.next_run_time.isoformat() if job else None 