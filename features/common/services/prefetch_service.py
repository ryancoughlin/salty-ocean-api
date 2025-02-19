import asyncio
import logging
from typing import Set, List
from datetime import datetime, timezone, timedelta
import time
from asyncio import Queue

from features.stations.services.station_service import StationService
from features.waves.services.wave_data_service import WaveDataService
from features.wind.services.wind_service import WindService
from features.common.models.station_types import Station

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for NOAA API requests."""
    def __init__(self, requests_per_minute: int = 15):
        self.requests_per_minute = requests_per_minute
        self.interval = 60 / requests_per_minute  # Time between requests
        self.last_request = 0.0
        self._lock = asyncio.Lock()
        self._error_backoff = 1  # Initial backoff in minutes
        self._max_backoff = 30  # Maximum backoff in minutes
        self._consecutive_errors = 0

    async def acquire(self):
        """Wait for rate limit if needed."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self.last_request
            
            # Apply exponential backoff if we've had errors
            if self._consecutive_errors > 0:
                backoff = min(self._error_backoff * (2 ** (self._consecutive_errors - 1)), self._max_backoff)
                logger.warning(f"Rate limit backoff: {backoff} minutes due to {self._consecutive_errors} consecutive errors")
                await asyncio.sleep(backoff * 60)  # Convert to seconds
            elif time_since_last < self.interval:
                delay = self.interval - time_since_last
                await asyncio.sleep(delay)
                
            self.last_request = time.time()

    def record_error(self):
        """Record an error and increase backoff."""
        self._consecutive_errors += 1

    def record_success(self):
        """Record a success and reset backoff."""
        self._consecutive_errors = 0

class PrefetchService:
    def __init__(
        self,
        station_service: StationService,
        wave_service: WaveDataService,
        wind_service: WindService,
        batch_size: int = 5,
        requests_per_minute: int = 15
    ):
        self.station_service = station_service
        self.wave_service = wave_service
        self.wind_service = wind_service
        self._background_tasks: Set[asyncio.Task] = set()
        self._is_prefetching = False
        self.batch_size = batch_size
        self.rate_limiter = RateLimiter(requests_per_minute)
        self._last_model_cycle = None

    def _should_prefetch(self, current_cycle: str) -> bool:
        """Determine if we should prefetch based on model cycle changes."""
        if self._last_model_cycle != current_cycle:
            self._last_model_cycle = current_cycle
            return True
        return False

    async def prefetch_station_data(self, station: Station):
        """Pre-fetch all data for a single station."""
        start_time = datetime.now(timezone.utc)
        try:
            logger.debug(f"Pre-fetching data for station {station.station_id}")
            
            # Rate limit each request individually
            for attempt in range(2):  # Allow one retry
                try:
                    await self.rate_limiter.acquire()
                    wave_forecast = await self.wave_service.get_station_forecast(station.station_id)
                    self.rate_limiter.record_success()
                    break
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        self.rate_limiter.record_error()
                        if attempt == 0:
                            logger.warning(f"Rate limited on wave forecast, retrying after backoff")
                            continue
                    raise

            # Similar pattern for wind data
            for attempt in range(2):
                try:
                    await self.rate_limiter.acquire()
                    wind_data = await self.wind_service.get_station_wind_data(station.station_id)
                    self.rate_limiter.record_success()
                    break
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        self.rate_limiter.record_error()
                        if attempt == 0:
                            logger.warning(f"Rate limited on wind data, retrying after backoff")
                            continue
                    raise

            # And wind forecast
            for attempt in range(2):
                try:
                    await self.rate_limiter.acquire()
                    wind_forecast = await self.wind_service.get_station_wind_forecast(station.station_id)
                    self.rate_limiter.record_success()
                    break
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        self.rate_limiter.record_error()
                        if attempt == 0:
                            logger.warning(f"Rate limited on wind forecast, retrying after backoff")
                            continue
                    raise
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"Successfully pre-fetched data for station {station.station_id} in {duration:.2f}s")
            return True
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Error pre-fetching data for station {station.station_id} after {duration:.2f}s: {str(e)}")
            return False

    async def process_station_batch(self, stations: List[Station]):
        """Process a batch of stations with rate limiting."""
        results = []
        for station in stations:
            success = await self.prefetch_station_data(station)
            results.append((station.station_id, success))
            
            # Add extra delay between stations if we've had errors
            if self.rate_limiter._consecutive_errors > 0:
                await asyncio.sleep(5)  # 5 second delay between stations if we've hit rate limits
                
        return results

    async def prefetch_all_stations(self):
        """Pre-fetch data for all stations in batches with rate limiting."""
        if self._is_prefetching:
            logger.warning("Pre-fetch already in progress, skipping")
            return

        self._is_prefetching = True
        start_time = datetime.now(timezone.utc)
        try:
            logger.info("Starting pre-fetch for all stations")
            stations = self.station_service.get_stations()
            total_stations = len(stations)
            
            # Process stations in batches
            results = []
            for i in range(0, total_stations, self.batch_size):
                batch = stations[i:i + self.batch_size]
                logger.info(f"Processing batch {i//self.batch_size + 1}/{(total_stations + self.batch_size - 1)//self.batch_size}")
                batch_results = await self.process_station_batch(batch)
                results.extend(batch_results)
                
                # Add longer delay between batches
                await asyncio.sleep(10)  # 10 second delay between batches
            
            # Log summary
            successful = sum(1 for _, success in results if success)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"Completed pre-fetch: {successful}/{total_stations} stations successful "
                f"in {duration:.2f}s"
            )
            
            # Log failed stations
            failed = [(station_id, success) for station_id, success in results if not success]
            if failed:
                logger.warning(f"Failed stations: {[station_id for station_id, _ in failed]}")
                
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Error during pre-fetch after {duration:.2f}s: {str(e)}")
        finally:
            self._is_prefetching = False

    def start_background_prefetch(self):
        """Start pre-fetch in background without blocking."""
        task = asyncio.create_task(self.prefetch_all_stations())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def cleanup(self):
        """Cancel and cleanup any running background tasks."""
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear() 