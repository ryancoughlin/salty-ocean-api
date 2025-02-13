import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json

from services.wave_data_processor import WaveDataProcessor
from repositories.station_repo import StationRepository
from core.config import settings
from pathlib import Path
from services.weather_summary_service import WeatherSummaryService

logger = logging.getLogger(__name__)

class PrefetchService:
    """Service for prefetching wave model forecast data."""
    
    def __init__(self, wave_processor: WaveDataProcessor):
        self.wave_processor = wave_processor
        self.station_repo = StationRepository(Path('ndbcStations.json'))
        self.summary_service = WeatherSummaryService()
        self.semaphore = asyncio.Semaphore(4)  # Limit concurrent requests
        self._prefetch_lock = asyncio.Lock()  # Lock to prevent concurrent prefetches
        
    async def _process_station_forecast(self, station: dict) -> None:
        """Helper to process forecast for a single station with semaphore."""
        async with self.semaphore:
            try:
                station_id = station["id"]
                logger.debug(f"Prefetching forecast for station {station_id}")
                start_time = datetime.now()
                
                # Process forecast in executor to not block event loop
                forecast = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.wave_processor.process_station_forecast,
                    station_id
                )
                
                if forecast and forecast.get('forecasts'):
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.summary_service.generate_summary,
                        forecast['forecasts'],
                        forecast['metadata']
                    )
                    logger.debug(f"Generated summary for station {station_id}")
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Completed forecast and summary for {station_id} in {duration:.2f}s")
                
            except Exception as e:
                logger.error(f"Error processing forecast/summary for station {station_id}: {str(e)}")
        
    async def prefetch_wave_forecasts(self) -> None:
        """Prefetch wave model forecasts for all stations."""
        async with self._prefetch_lock:
            try:
                logger.info("Starting wave forecast and summary prefetch")
                start_time = datetime.now()
                
                model_run, date = self.wave_processor.get_current_model_run()
                dataset = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.wave_processor.load_dataset,
                    model_run,
                    date
                )
                
                if dataset is None:
                    logger.error("Failed to load dataset for prefetch")
                    return
                
                stations = self.station_repo.load_stations()
                logger.info(f"Processing forecasts and summaries for {len(stations)} stations")
                
                tasks = []
                for station in stations:
                    task = asyncio.create_task(
                        self._process_station_forecast(station)
                    )
                    tasks.append(task)
                
                if tasks:
                    try:
                        await asyncio.wait_for(asyncio.gather(*tasks), timeout=900)
                    except asyncio.TimeoutError:
                        logger.error("Prefetch timed out after 15 minutes")
                    except Exception as e:
                        logger.error(f"Error during prefetch: {str(e)}")
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Completed wave forecast and summary prefetch for {len(stations)} stations in {duration:.2f}s")
                
            except Exception as e:
                logger.error(f"Error during wave forecast and summary prefetch: {str(e)}")
                raise
            
    async def prefetch_all(self) -> None:
        """Run all prefetch tasks."""
        try:
            await self.prefetch_wave_forecasts()
            logger.info("Completed all prefetch tasks")
        except Exception as e:
            logger.error(f"Error in prefetch_all: {str(e)}")
            raise 