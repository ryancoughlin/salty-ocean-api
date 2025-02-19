import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.append(str(Path(__file__).parent.parent))

from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.common.models.station_types import Station
from features.common.services.model_run_service import ModelRunService
from core.cache import init_cache

async def main():
    # Initialize cache
    await init_cache()
    
    station_id = "44098"
    station = Station(
        station_id=station_id,
        name="Jeffrey's Ledge, NH",
        location={
            "type": "Point",
            "coordinates": [-70.171, 42.8]
        },
        type="buoy"
    )
    
    model_run_service = ModelRunService()
    client = NOAAGFSClient(model_run_service)
    
    try:
        forecast = await client.get_station_forecast(station_id, station)
        
        print(f"\nStation: {station_id} - {station.name}")
        print(f"GFS Model Run: {forecast.cycle.date} {forecast.cycle.hour}Z\n")
        
        now = datetime.now(timezone.utc)
        # Print next 24 hours of forecasts
        for point in forecast.forecasts:
            if point.timestamp < now:
                continue
                
            if point.timestamp > now + timedelta(hours=24):
                break
                
            print(f"\nForecast for {point.timestamp.strftime('%Y-%m-%d %H:%M')} UTC:")
            for i, wave in enumerate(point.waves, 1):
                print(f"Wave Component {i}:")
                print(f"  Height: {wave.height_m:.1f}m ({wave.height_ft:.1f}ft)")
                print(f"  Period: {wave.period:.1f}s")
                print(f"  Direction: {wave.direction:.0f}°")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main()) 