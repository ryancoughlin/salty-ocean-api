import logging
import asyncio
from datetime import datetime, timedelta, timezone
from features.waves.services.prefetch_service import PrefetchService
from features.weather.services.gfs_service import GFSForecastManager
from fastapi_cache import FastAPICache

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(
        self,
        prefetch_service: PrefetchService,
        gfs_manager: GFSForecastManager
    ):
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
                    # Update GFS data
                    if await self.gfs_manager.update_forecast():
                        logger.info("New GFS data downloaded")
                        # Prefetch new forecasts
                        await self.prefetch_service.prefetch_all()
                        # Clear caches
                        await FastAPICache.clear(namespace="wave_forecast")
                        await FastAPICache.clear(namespace="gfs_wave_forecast")
                        logger.info("Wave forecasts updated and caches cleared")
                    else:
                        logger.info("No new GFS data available")
                        
                    # Wait before next check (10 minutes)
                    await asyncio.sleep(600)
                    
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {str(e)}")
                    await asyncio.sleep(60)  # Wait a minute before retrying
                    
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
            raise 