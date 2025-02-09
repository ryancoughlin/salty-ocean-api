import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import List, Optional
import time

from core.config import settings
from utils.model_time import get_latest_model_run

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
        self._rate_limiter = asyncio.Semaphore(5)  # Control concurrent downloads
        self._session = None
        
    def get_current_model_run(self) -> tuple[str, str]:
        """Get the latest available model run based on current UTC time."""
        return get_latest_model_run()

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
            first_file = f"gfswave.t{self.current_model_run}z.{model_name}.f000.grib2"  # Start at f000
            last_file = f"gfswave.t{self.current_model_run}z.{model_name}.f120.grib2"   # End at f120
            
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
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy initialize and reuse session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _get_files_to_download(self, model_run: str, date: str) -> List[tuple]:
        """Get list of files that need downloading."""
        base_url = f"{settings.base_url}/gfs.{date}/{model_run}/wave/gridded"
        files = []
        
        for hour in settings.forecast_files:
            filename = f"gfswave.t{model_run}z.{settings.models['atlantic']['name']}.f{str(hour).zfill(3)}.grib2"
            local_path = self.data_dir / filename
            
            if not local_path.exists():
                files.append((f"{base_url}/{filename}", local_path))
        
        return files
    
    async def download_file(self, url: str, file_path: Path) -> bool:
        """Download single file with rate limiting."""
        async with self._rate_limiter:
            session = await self._get_session()
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        file_path.write_bytes(content)
                        return True
                    return False
            except Exception as e:
                logger.error(f"Error downloading {url}: {str(e)}")
                return False
    
    async def download_model_data(self) -> bool:
        """Download all needed model data concurrently."""
        try:
            model_run, date = self.get_current_model_run()
            files = self._get_files_to_download(model_run, date)
            
            if not files:
                logger.info("No new files to download")
                return True
            
            tasks = [self.download_file(url, path) for url, path in files]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if r is True)
            return success_count == len(files)
            
        except Exception as e:
            logger.error(f"Error downloading model data: {str(e)}")
            return False 