import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from core.config import settings
from services.prefetch_service import PrefetchService
from fastapi_cache import FastAPICache

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduling model data updates."""
    
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
        self._task: Optional[asyncio.Task] = None
        
    async def _update_model_data(self, run_hour: int):
        """Update model data for a specific run hour."""
        try:
            logger.debug(f"Checking for {run_hour:02d}z model run updates...")
            
            # Check for new data
            if await self.wave_downloader.download_latest():
                # Flush the cache before loading new data
                logger.info("New model data available - flushing cache")
                await FastAPICache.clear()
                
                # Load new data
                if await self.wave_processor.preload_dataset():
                    # Prefetch forecasts for all stations with new data
                    await self.prefetch_service.prefetch_all()
                else:
                    logger.error("Failed to load new model data")
            else:
                logger.debug(f"No updates needed for {run_hour:02d}z run")
                
        except Exception as e:
            logger.error(f"Error during {run_hour:02d}z model update: {str(e)}")
            
    async def _schedule_updates(self):
        """Schedule model updates."""
        while True:
            try:
                now = datetime.utcnow()
                
                # Schedule updates 1.5 hours after each model run
                # Model runs are at 00z, 06z, 12z, and 18z
                for run_hour in [0, 6, 12, 18]:
                    # Calculate next update time
                    update_time = now.replace(hour=run_hour, minute=30, second=0, microsecond=0)
                    if update_time <= now:
                        update_time += timedelta(hours=6)
                        
                    # Log scheduled update
                    logger.info(f"Scheduled update for {run_hour}z run at {update_time.strftime('%H:%M')} UTC")
                    
                    # Wait until update time
                    wait_seconds = (update_time - now).total_seconds()
                    if wait_seconds > 0:
                        await asyncio.sleep(wait_seconds)
                        await self._update_model_data(run_hour)
                    
            except Exception as e:
                logger.error(f"Error in scheduler: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
                
    async def start(self):
        """Start the scheduler."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._schedule_updates())
            logger.info("Scheduler started")
            
    async def stop(self):
        """Stop the scheduler."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Scheduler stopped")
            
    def get_next_run_time(self, job_id: str):
        """Get next scheduled run time."""
        job = self.scheduler.get_job(job_id)
        return job.next_run_time if job else None 