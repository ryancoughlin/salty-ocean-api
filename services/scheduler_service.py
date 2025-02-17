import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from services.prefetch_service import PrefetchService
from services.weather.gfs_service import GFSForecastManager
from fastapi_cache import FastAPICache

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(
        self,
        wave_processor: WaveDataProcessor,
        wave_downloader: WaveDataDownloader,
        prefetch_service: PrefetchService,
        gfs_manager: GFSForecastManager
    ):
        self.wave_processor = wave_processor
        self.wave_downloader = wave_downloader
        self.prefetch_service = prefetch_service
        self.gfs_manager = gfs_manager
        self.scheduler = AsyncIOScheduler()
        self._task = None

    async def _update_gfs_data(self) -> None:
        """Update GFS forecast data."""
        try:
            await self.gfs_manager.update_forecast()
            # Clear GFS-related caches when new data is available
            await FastAPICache.clear(namespace="gfs_wave_forecast")
            await FastAPICache.clear(namespace="wind_data")
            await FastAPICache.clear(namespace="wind_forecast")
            logger.info("Cleared GFS-related caches after update")
        except Exception as e:
            logger.error(f"Failed to update GFS data: {str(e)}")

    async def _update_wave_data(self, run_hour: int) -> None:
        """Update wave model data for a specific run hour."""
        try:
            if await self.wave_downloader.download_latest():
                logger.info(f"New wave model data downloaded for {run_hour}z run")
                if self.wave_processor.get_dataset() is not None:
                    await self.prefetch_service.prefetch_all()
                    # Clear wave-related caches when new data is available
                    await FastAPICache.clear(namespace="wave_forecast")
                    await FastAPICache.clear(namespace="offshore_data")
                    logger.info("Cleared wave-related caches after update")
                    logger.info("Wave model data processed and prefetched successfully")
                else:
                    logger.error("Failed to process wave model data")
            else:
                logger.info(f"No new wave model data available for {run_hour}z run")
        except Exception as e:
            logger.error(f"Error updating wave data for {run_hour}z run: {str(e)}")

    async def start(self) -> None:
        """Start the scheduler."""
        try:
            # Schedule updates for both GFS and wave data 3.5 hours after model runs
            # Based on GFS publication times (~3:30 after each run)
            for base_hour in [0, 6, 12, 18]:
                update_hour = (base_hour + 3) % 24
                
                # Schedule GFS updates
                self.scheduler.add_job(
                    self._update_gfs_data,
                    CronTrigger(hour=update_hour, minute=30),
                    id=f"gfs_update_{base_hour}",
                    replace_existing=True
                )
                logger.info(f"Scheduled GFS update for {base_hour:02d}z run at {update_hour:02d}:30 UTC")

                # Schedule wave model updates
                self.scheduler.add_job(
                    self._update_wave_data,
                    CronTrigger(hour=update_hour, minute=30),
                    args=[base_hour],
                    id=f"wave_update_{base_hour}",
                    replace_existing=True
                )
                logger.info(f"Scheduled wave update for {base_hour:02d}z run at {update_hour:02d}:30 UTC")

            self.scheduler.start()
            logger.info("Scheduler started successfully")

        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            raise

    async def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped") 