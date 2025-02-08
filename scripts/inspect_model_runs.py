import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import aiohttp
import xarray as xr
import pandas as pd
import sys
import os

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ModelRunInspector:
    def __init__(self):
        self.session = None
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive'
        }

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def get_url(self, model_run, date, hour):
        base_url = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
        return f"{base_url}/gfs.{date}/{model_run}/wave/gridded/gfswave.t{model_run}z.{settings.models['atlantic']['name']}.f{str(hour).zfill(3)}.grib2"

    async def download_file(self, url, output_path):
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        f.write(await response.read())
                    logging.info(f"Downloaded {os.path.basename(output_path)}")
                    return True
                else:
                    logging.error(f"Failed to download {url}: HTTP {response.status}")
                    return False
        except Exception as e:
            logging.error(f"Error downloading {url}: {str(e)}")
            return False

    def inspect_file(self, file_path, model_run, forecast_hour):
        try:
            # Use cfgrib engine with filter_by_keys to properly handle time dimension
            ds = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={
                'filter_by_keys': {'typeOfLevel': 'surface'}
            })
            
            # Calculate the actual forecast time
            model_run_time = pd.Timestamp(f"2025-02-06T{model_run}:00:00Z")
            forecast_time = model_run_time + pd.Timedelta(hours=forecast_hour)
            
            result = {
                'file': os.path.basename(file_path),
                'model_run': f"{model_run}z",
                'forecast_hour': forecast_hour,
                'forecast_time': forecast_time,
                'variables': list(ds.data_vars.keys()),
            }
            
            # Get significant wave height statistics if available
            if 'swh' in ds:
                result['swh_stats'] = {
                    'min': float(ds.swh.min().values),
                    'max': float(ds.swh.max().values),
                    'mean': float(ds.swh.mean().values)
                }
            
            ds.close()
            return result
            
        except Exception as e:
            logging.error(f"Error inspecting {file_path}: {str(e)}")
            return None

    async def process_model_run(self, model_run, date):
        logging.info(f"\nProcessing model run {date} {model_run}z")
        results = []
        
        for hour in range(24):  # Process first 24 forecast hours
            url = self.get_url(model_run, date, hour)
            filename = os.path.basename(url)
            output_path = os.path.join(self.data_dir, filename)
            
            if await self.download_file(url, output_path):
                await asyncio.sleep(0.5)  # Rate limiting
                result = self.inspect_file(output_path, model_run, hour)
                if result:
                    results.append(result)
                    logging.info(f"Forecast time: {result['forecast_time']}")
                    if 'swh_stats' in result:
                        logging.info(f"SWH stats: {result['swh_stats']}")
        
        return results

async def main():
    inspector = ModelRunInspector()
    await inspector.init_session()
    
    try:
        date = "20250206"
        all_forecasts = []
        
        # Process all model runs for the day
        for model_run in ["00", "06", "12", "18"]:
            results = await inspector.process_model_run(model_run, date)
            if results:
                all_forecasts.extend(results)
        
        # Sort all forecasts by time and analyze coverage
        if all_forecasts:
            all_forecasts.sort(key=lambda x: x['forecast_time'])
            
            logging.info("\nForecast Coverage Analysis:")
            logging.info(f"Total forecasts: {len(all_forecasts)}")
            logging.info(f"Earliest forecast: {all_forecasts[0]['forecast_time']}")
            logging.info(f"Latest forecast: {all_forecasts[-1]['forecast_time']}")
            
            # Check for gaps in coverage
            for i in range(1, len(all_forecasts)):
                time_diff = all_forecasts[i]['forecast_time'] - all_forecasts[i-1]['forecast_time']
                if time_diff > pd.Timedelta(hours=1):
                    logging.warning(f"Gap in coverage between {all_forecasts[i-1]['forecast_time']} and {all_forecasts[i]['forecast_time']} ({time_diff})")
            
            # Print summary of forecasts by model run
            logging.info("\nForecasts by Model Run:")
            for model_run in ["00z", "06z", "12z", "18z"]:
                run_forecasts = [f for f in all_forecasts if f['model_run'] == model_run]
                if run_forecasts:
                    logging.info(f"\n{model_run} run:")
                    for f in run_forecasts:
                        logging.info(f"  {f['forecast_time']}: SWH max={f['swh_stats']['max']:.2f}m")
    
    finally:
        await inspector.close_session()

if __name__ == "__main__":
    asyncio.run(main()) 