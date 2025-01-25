import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json

from services.wave_data_processor import WaveDataProcessor
from repositories.station_repo import StationRepository
from core.config import settings
from pathlib import Path

logger = logging.getLogger(__name__)

class PrefetchService:
    """Service for prefetching wave model forecast data."""
    
    def __init__(self):
        self.wave_processor = WaveDataProcessor()
        self.station_repo = StationRepository(Path('ndbcStations.json'))
        self.semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        
    async def _process_station_forecast(self, station: dict, model_run: str, date: str) -> None:
        """Helper to process forecast for a single station with semaphore."""
        async with self.semaphore:
            try:
                station_id = station["id"]
                logger.debug(f"Processing forecast for station {station_id}")
                # Since process_station_forecast is not async, run it in executor
                forecast = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.wave_processor.process_station_forecast,
                    station_id,
                    model_run,
                    date
                )
                logger.debug(f"Successfully processed forecast for {station_id}")
            except Exception as e:
                logger.error(f"Error processing forecast for station {station_id}: {str(e)}")
        
    async def prefetch_wave_forecasts(self) -> None:
        """Prefetch wave model forecasts for all stations."""
        try:
            logger.info("Starting wave forecast prefetch")
            model_run, date = self.wave_processor.get_current_model_run()
            logger.info(f"Current model run: {date} {model_run}z")
            
            # Skip download if it was already done by model update
            if not self.wave_processor.has_current_data():
                logger.info("Downloading new model data")
                success = await self.wave_processor.update_model_data()
                if not success:
                    logger.error("Failed to download model data")
                    return
            else:
                logger.info("Using existing model data")
            
            # Load stations and process forecasts
            stations = self.station_repo.load_stations()
            
            tasks = []
            for station in stations:
                task = asyncio.create_task(
                    self._process_station_forecast(station, model_run, date)
                )
                tasks.append(task)
            
            if tasks:
                # Wait for all tasks with timeout
                try:
                    await asyncio.wait_for(asyncio.gather(*tasks), timeout=600)  # 10 minute timeout
                except asyncio.TimeoutError:
                    logger.error("Prefetch timed out after 10 minutes")
                except Exception as e:
                    logger.error(f"Error during prefetch: {str(e)}")
                    
            logger.info("Completed wave forecast prefetch")
            
        except Exception as e:
            logger.error(f"Error during wave forecast prefetch: {str(e)}")
            
    async def prefetch_all(self) -> None:
        """Run all prefetch tasks."""
        try:
            await self.prefetch_wave_forecasts()
            logger.info("Completed all prefetch tasks")
        except Exception as e:
            logger.error(f"Error in prefetch_all: {str(e)}")
            raise 