import logging
import asyncio
from datetime import datetime, timedelta
from features.waves.services.wave_data_processor import WaveDataProcessor
from features.waves.services.wave_data_downloader import WaveDataDownloader
from features.waves.services.prefetch_service import PrefetchService
from features.weather.services.gfs_service import GFSForecastManager

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
        self._task = None
        self._running = False
        
    async def start(self):
        """Start the scheduler."""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Scheduler started")
        
    async def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")
        
    async def _run(self):
        """Main scheduler loop."""
        try:
            while self._running:
                try:
                    # Check for new wave model data
                    download_success = await self.wave_downloader.download_latest()
                    
                    if download_success:
                        logger.info("New wave model data downloaded")
                        # Reload wave processor dataset
                        if await self.wave_processor.preload_dataset() is None:
                            logger.error("Failed to load new wave model data")
                    else:
                        # If download failed, check if it was due to 403
                        if self.wave_downloader._download_state.get("error_type") == "forbidden":
                            logger.warning("NOAA API access denied - continuing with existing data if available")
                            # Don't try to reload data, just keep using existing
                            await asyncio.sleep(self.wave_downloader._download_state["retry_after"])
                            continue
                            
                        logger.warning("No new wave model data available, using existing data")
                        
                    # Wait before next check (10 minutes)
                    await asyncio.sleep(600)
                    
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {str(e)}")
                    await asyncio.sleep(60)  # Wait a minute before retrying
                    
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
            raise
        finally:
            # Ensure resources are cleaned up
            self.wave_processor.close_dataset() 