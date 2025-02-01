import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from core.config import settings
from services.prefetch_service import PrefetchService

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
        
    async def _update_model_data(self):
        """Download and process new model data."""
        try:
            current_utc = datetime.now(timezone.utc)
            logger.info(f"Starting model data update at {current_utc.strftime('%Y-%m-%d %H:%M UTC')}")
            success = await self.wave_downloader.download_model_data()
            
            if success:
                logger.info("Successfully downloaded new model data")
                await self.wave_processor.preload_dataset()
                
                logger.info("Processing forecasts for all stations...")
                await self.prefetch_service.prefetch_wave_forecasts()
            else:
                # If initial download fails, retry after 15 minutes
                logger.warning("Initial download failed, scheduling retry in 15 minutes")
                self.scheduler.add_job(
                    self._update_model_data,
                    'date',
                    run_date=datetime.now() + timedelta(minutes=15),
                    id='retry_download',
                    replace_existing=True
                )
                
        except Exception as e:
            logger.error(f"Error updating model data: {str(e)}")
    
    def start(self):
        """Start the scheduler."""
        if self.scheduler.running:
            return
            
        # Schedule updates based on NCEP processing times
        # NOAA runs at 00, 06, 12, 18 UTC
        # Wave products start ~3.5 hours after model run
        # So we schedule at 03:30, 09:30, 15:30, 21:30 UTC
        current_utc = datetime.now(timezone.utc)
        logger.info(f"Starting scheduler at {current_utc.strftime('%Y-%m-%d %H:%M UTC')}")
        
        for model_run in settings.model_runs:
            # Convert model_run to int before arithmetic
            run_hour = int(model_run)
            update_hour = (run_hour + 3) % 24  # Add 3 hours to model run time
            
            self.scheduler.add_job(
                self._update_model_data,
                CronTrigger(hour=update_hour, minute=30),  # Run at :30 past the hour
                id=f"wave_forecasts_{run_hour}z",
                name=f"Wave Model Update {run_hour}Z",
                misfire_grace_time=3600,
                coalesce=True
            )
            logger.info(f"Scheduled update for {run_hour}z run at {update_hour:02d}:30 UTC")
            
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