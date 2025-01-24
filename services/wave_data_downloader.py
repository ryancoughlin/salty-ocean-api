import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import List, Optional

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WaveDataDownloader:
    def __init__(self, data_dir: str = settings.data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.current_model_run = None
        self.current_date = None
        
    def get_current_model_run(self) -> tuple[str, str]:
        """Determine the current model run based on UTC time."""
        now = datetime.utcnow()
        current_hour = now.hour
        
        # Model runs take ~5 hours to become available
        if current_hour >= 23:
            model_run = "18"
        elif current_hour >= 17:
            model_run = "12"
        elif current_hour >= 11:
            model_run = "06"
        elif current_hour >= 5:
            model_run = "00"
        else:
            # Use previous day's 18z run
            model_run = "18"
            now -= timedelta(days=1)
            
        date = now.strftime("%Y%m%d")
        
        # Only update if different from current
        if model_run != self.current_model_run or date != self.current_date:
            logger.info(f"Updating to model run: {date} {model_run}z")
            self.current_model_run = model_run
            self.current_date = date
            
        return model_run, date
        
    def has_current_data(self) -> bool:
        """Check if we have data for the current model run."""
        if not self.current_model_run:
            self.get_current_model_run()
            
        # Check each region for required files
        for region in settings.models:
            model_name = settings.models[region]["name"]
            # Check first forecast hour file (f000)
            file_name = f"gfswave.t{self.current_model_run}z.{model_name}.f000.grib2"
            if not (self.data_dir / file_name).exists():
                logger.info(f"Missing file: {file_name}")
                return False
                        
        logger.info(f"Found existing data for model run {self.current_model_run}z")
        return True
        
    async def download_file(
        self,
        session: aiohttp.ClientSession,
        url: str,
        file_path: Path,
        retries: int = 3
    ) -> bool:
        """Download a single file with retries."""
        for attempt in range(retries + 1):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        file_path.write_bytes(content)
                        logger.info(f"Downloaded: {file_path.name}")
                        return True
                    elif response.status == 404:
                        logger.warning(f"File not found: {url}")
                        return False
                    else:
                        logger.error(f"Failed to download {url}: Status {response.status}")
                        
            except Exception as e:
                logger.error(f"Error downloading {url}: {str(e)}")
                if attempt < retries:
                    await asyncio.sleep(settings.request["retry_delay"])
                continue
                
        return False
        
    async def download_model_data(self, regions: Optional[List[str]] = None) -> bool:
        """Download GRIB2 files for specified regions and current model run."""
        if regions is None:
            regions = list(settings.models.keys())
            
        model_run, date = self.get_current_model_run()
        
        # Always check for existing data first
        if self.has_current_data():
            logger.info(f"Using existing data from model run {model_run}z {date}")
            return True
            
        logger.info(f"Downloading data for model run: {date} {model_run}z")
        
        # Construct base URL for this model run
        base_url = f"{settings.base_url}/gfs.{date}/{model_run}/wave/gridded"
        logger.info(f"Base URL: {base_url}")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.request["timeout"])) as session:
            tasks = []
            
            for region in regions:
                model_name = settings.models[region]["name"]
                
                # Follow NOAA's forecast hour pattern
                hours = list(range(0, 121))  # 0-120 hourly
                hours.extend(range(121, 385, 3))  # 121-384 every 3 hours
                
                for hour in hours:
                    padded_hour = str(hour).zfill(3)
                    file_name = f"gfswave.t{model_run}z.{model_name}.f{padded_hour}.grib2"
                    file_path = self.data_dir / file_name
                    
                    # Skip if file exists
                    if file_path.exists():
                        logger.debug(f"Skipping {file_name} (exists)")
                        continue
                    
                    tasks.append(self.download_file(session, url=f"{base_url}/{file_name}", file_path=file_path))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
                logger.info(f"Downloaded {success_count} of {len(tasks)} files")
                return success_count > 0
            
            logger.info("No new files to download")
            return True
            
    async def cleanup_old_files(self):
        """Remove files from different model runs."""
        if not self.current_model_run:
            self.get_current_model_run()
            
        count = 0
        for file_path in self.data_dir.glob("*.grib2"):
            # Check if file is from current model run
            if not file_path.name.startswith(f"gfswave.t{self.current_model_run}z"):
                file_path.unlink()
                count += 1
                
        if count > 0:
            logger.info(f"Cleaned up {count} old files") 