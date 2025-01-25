import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import List, Optional
import time

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WaveDataDownloader:
    def __init__(self, data_dir: str = settings.data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.current_model_run = None
        self.current_date = None
        self._last_request_time = 0
        self._request_interval = 1.0  # Minimum seconds between requests
        self._download_state = {
            "last_attempt": None,
            "last_success": None,
            "retry_after": 300  # 5 minutes default retry
        }
        
    def get_current_model_run(self) -> tuple[str, str]:
        """Get the latest available model run based on current UTC time."""
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        
        # Model runs are at 00, 06, 12, 18 UTC
        # Data is available ~5 hours after run time
        model_runs = [0, 6, 12, 18]
        
        # Find the latest run that should have data available
        latest_run = max((run for run in model_runs if current_hour >= run + 5), default=18)
        
        # If we're before the first run + delay of the day, use previous day's last run
        if latest_run == 18 and current_hour < model_runs[0] + 5:
            now = now - timedelta(days=1)
        
        return str(latest_run).zfill(2), now.strftime("%Y%m%d")

    def should_attempt_download(self) -> bool:
        """Check if we should attempt a download based on previous attempts."""
        now = time.time()
        if not self._download_state["last_attempt"]:
            return True
            
        # If last attempt was successful, only try again for new model run
        if self._download_state["last_success"]:
            current_run = self.get_current_model_run()
            if current_run != (self.current_model_run, self.current_date):
                return True
            return False
            
        # If last attempt failed, wait for retry_after period
        time_since_attempt = now - self._download_state["last_attempt"]
        return time_since_attempt >= self._download_state["retry_after"]
        
    def has_current_data(self) -> bool:
        """Check if we have data for the current model run."""
        if not self.current_model_run:
            self.get_current_model_run()
            
        # Check each region for required files
        for region in settings.models:
            model_name = settings.models[region]["name"]
            # Check first and last forecast hour files
            first_file = f"gfswave.t{self.current_model_run}z.{model_name}.f120.grib2"  # Start at f120
            last_file = f"gfswave.t{self.current_model_run}z.{model_name}.f384.grib2"
            
            if not (self.data_dir / first_file).exists() or not (self.data_dir / last_file).exists():
                return False
                        
        logger.info(f"Found existing data for model run {self.current_model_run}z")
        return True

    async def _enforce_rate_limit(self):
        """Enforce minimum time between requests to avoid rate limiting."""
        now = time.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._request_interval:
            await asyncio.sleep(self._request_interval - time_since_last)
        self._last_request_time = time.time()
        
    async def download_file(
        self,
        session: aiohttp.ClientSession,
        url: str,
        file_path: Path,
        retries: int = 3
    ) -> bool:
        """Download a single file with retries and rate limiting."""
        await self._enforce_rate_limit()
        
        for attempt in range(retries + 1):
            try:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.read()
                        file_path.write_bytes(content)
                        return True
                    elif response.status == 404:
                        logger.warning(f"File not found: {url}")
                        return False
                    elif response.status == 429 or response.status == 403:
                        retry_after = int(response.headers.get('Retry-After', 300))
                        logger.warning(f"Rate limited by NOAA (status {response.status}). Retry after {retry_after}s")
                        self._download_state["retry_after"] = retry_after
                        await asyncio.sleep(min(30, 2 ** attempt))
                        self._request_interval = min(5.0, self._request_interval * 1.5)
                        continue
                    else:
                        logger.error(f"Failed to download {url}: Status {response.status}")
                        
            except Exception as e:
                logger.error(f"Error downloading {url}: {str(e)}")
                if attempt < retries:
                    await asyncio.sleep(settings.request["retry_delay"])
                continue
                
        return False
        
    async def download_model_data(self) -> bool:
        """Download wave model data for the current run."""
        try:
            model_run, date = self.get_current_model_run()
            logger.info(f"Downloading data for model run: {date} {model_run}z")
            
            base_url = f"{settings.base_url}/gfs.{date}/{model_run}/wave/gridded"
            logger.info(f"Base URL: {base_url}")
            
            # Track overall success
            total_files = 0
            downloaded_files = 0
            
            # Process each region
            for region, config in settings.models.items():
                logger.info(f"Processing region: {region}")
                model_name = config["name"]
                
                # Build list of files to download
                files_to_download = []
                for hour in settings.forecast_files:
                    filename = f"gfswave.t{model_run}z.{model_name}.f{str(hour).zfill(3)}.grib2"
                    local_path = Path(settings.data_dir) / filename
                    
                    total_files += 1  # Count total expected files
                    
                    # Skip if file already exists for current model run
                    if local_path.exists():
                        logger.debug(f"Skipping {filename} - already exists")
                        downloaded_files += 1
                        continue
                        
                    files_to_download.append((
                        f"{base_url}/gfswave.t{model_run}z.{model_name}.f{str(hour).zfill(3)}.grib2",
                        local_path
                    ))
                
                if not files_to_download:
                    logger.info(f"No new files to download for {region}")
                    continue
                    
                logger.info(f"Need to process {len(files_to_download)} files for {region}")
                
                # Process files in batches
                batch_size = 5
                for i in range(0, len(files_to_download), batch_size):
                    batch = files_to_download[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    logger.info(f"Processing batch {batch_num} ({len(batch)} files)")
                    
                    # Download batch concurrently
                    tasks = []
                    for url, local_path in batch:
                        task = asyncio.create_task(self._download_file(url, local_path))
                        tasks.append(task)
                    
                    # Wait for batch to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Count successes and handle errors
                    batch_successes = sum(1 for r in results if r is True)
                    downloaded_files += batch_successes
                    
                    logger.info(f"Batch {batch_num}: Successfully downloaded {batch_successes}/{len(batch)} files")
                    
                    # Check for errors
                    for result, (url, _) in zip(results, batch):
                        if isinstance(result, Exception):
                            logger.error(f"Error downloading {url}: {str(result)}")
            
            # Return overall success status
            success = downloaded_files == total_files
            if success:
                logger.info(f"Successfully downloaded all {downloaded_files} files")
            else:
                logger.warning(f"Downloaded {downloaded_files}/{total_files} files")
            
            return success
            
        except Exception as e:
            logger.error(f"Error downloading wave model data: {str(e)}")
            return False

    async def _download_file(
        self,
        url: str,
        file_path: Path
    ) -> bool:
        """Download a single file and return success status."""
        try:
            async with aiohttp.ClientSession() as session:
                return await self.download_file(session, url, file_path)
        except Exception as e:
            logger.error(f"Error downloading {url}: {str(e)}")
            return False 