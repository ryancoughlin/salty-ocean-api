from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import os
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio

from core.config import settings
from core.logging_config import setup_logging
from core.cache import init_cache
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

# Feature routes
from features.waves.routes.wave_routes import router as wave_router
from features.waves.routes.wave_routes_v2 import router as wave_router_v2
from features.tides.routes.tide_routes import router as tide_router
from features.wind.routes.wind_routes import router as wind_router
from features.stations.routes.station_routes import router as station_router

# Services and clients
from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.waves.services.gfs_wave_client import GFSWaveClient
from features.waves.services.wave_data_service import WaveDataService
from features.waves.services.wave_data_service_v2 import WaveDataServiceV2
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient
from features.stations.services.station_service import StationService
from features.stations.services.condition_summary_service import ConditionSummaryService
from features.wind.services.wind_service import WindService
from features.wind.services.gfs_wind_client import GFSWindClient
from features.wind.services.prefetch_service import WindPrefetchService
from features.common.services.model_run_service import ModelRunService
from features.tides.services.tide_service import TideService

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        # Create required directories
        Path("data").mkdir(exist_ok=True)
        Path("downloaded_data").mkdir(exist_ok=True)
        Path(settings.cache_dir).mkdir(exist_ok=True)

        # Initialize in-memory cache
        FastAPICache.init(InMemoryBackend(), prefix="salty-ocean")
        await init_cache()

        # Initialize model run service as single source of truth
        model_run_service = ModelRunService()
        current_model_run = await model_run_service.get_latest_available_cycle()
        if not current_model_run:
            logger.error("Failed to get initial model run")
            raise Exception("Failed to get initial model run")
            
        # Store model run service and current model run in app state
        app.state.model_run_service = model_run_service
        app.state.current_model_run = current_model_run
            
        # Initialize services and clients
        station_service = StationService()
        buoy_client = NDBCBuoyClient()
        
        # Initialize clients with current model run
        print("\n📡 Creating GFS clients...")
        gfs_wave_client = NOAAGFSClient(model_run=current_model_run)
        gfs_wave_client_v2 = GFSWaveClient(model_run=current_model_run)
        gfs_wind_client = GFSWindClient(model_run=current_model_run)
        print("✅ GFS clients created")
        
        # Initialize wind prefetch service
        wind_prefetch_service = WindPrefetchService(gfs_client=gfs_wind_client)
        app.state.wind_prefetch_service = wind_prefetch_service
        
        # Download initial wave data
        print("\n📥 Downloading initial wave data...")
        await gfs_wave_client_v2.initialize()
        print("✅ Wave data downloaded")
        
        # Start prefetch in background
        async def run_initial_prefetch():
            try:
                print("\n📥 Starting wind data prefetch in background...")
                await wind_prefetch_service.prefetch_all_stations()
                print("✅ Wind data prefetch complete")
            except Exception as e:
                logger.error(f"Error in initial wind prefetch: {str(e)}")
        
        # Start prefetch task
        app.state.prefetch_task = asyncio.create_task(run_initial_prefetch())
        
        # Store services and clients in app state
        app.state.gfs_client = gfs_wave_client
        app.state.gfs_wave_client_v2 = gfs_wave_client_v2
        app.state.gfs_wind_client = gfs_wind_client
        app.state.station_service = station_service
        app.state.tide_service = TideService()
        app.state.wave_service = WaveDataService(
            gfs_client=gfs_wave_client,
            buoy_client=buoy_client,
            station_service=station_service
        )
        app.state.wave_service_v2 = WaveDataServiceV2(
            gfs_client=gfs_wave_client_v2,
            buoy_client=buoy_client,
            station_service=station_service
        )
        app.state.wind_service = WindService(
            gfs_client=gfs_wind_client,
            station_service=station_service
        )
        app.state.condition_summary_service = ConditionSummaryService(
            wind_service=app.state.wind_service,
            wave_service=app.state.wave_service_v2,
            station_service=station_service
        )
        
        # Start background tasks
        logger.info("Starting background tasks...")
        
        # Task to check for new model runs
        async def check_model_runs():
            while True:
                try:
                    new_model_run = await model_run_service.get_latest_available_cycle()
                    if new_model_run and (
                        new_model_run.run_date != app.state.current_model_run.run_date or 
                        new_model_run.cycle_hour != app.state.current_model_run.cycle_hour
                    ):
                        logger.info("New model run detected, updating clients...")
                        # Update all clients with new model run
                        app.state.gfs_client.update_model_run(new_model_run)
                        app.state.gfs_wave_client_v2.update_model_run(new_model_run)
                        app.state.gfs_wind_client.update_model_run(new_model_run)
                        # Update wind prefetch with new model run
                        await app.state.wind_prefetch_service.handle_model_run_update(new_model_run)
                        # Update our reference to current model run in app state
                        app.state.current_model_run = new_model_run
                except Exception as e:
                    logger.error(f"Error checking for new model run: {str(e)}")
                finally:
                    # Check every 15 minutes
                    await asyncio.sleep(900)
                    
        # Start model run check task
        app.state.model_run_task = asyncio.create_task(check_model_runs())
        
        logger.info("🚀 App started")
        yield
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    finally:
        # Cancel all background tasks
        if hasattr(app.state, "model_run_task"):
            app.state.model_run_task.cancel()
            try:
                await app.state.model_run_task
            except asyncio.CancelledError:
                pass
            
        if hasattr(app.state, "prefetch_task"):
            app.state.prefetch_task.cancel()
            try:
                await app.state.prefetch_task
            except asyncio.CancelledError:
                pass
            
        # Cleanup wave client
        if hasattr(app.state, "wave_service_v2"):
            await app.state.wave_service_v2.gfs_client.close()
            
        logger.info("App shutdown")

app = FastAPI(
    title="Salty Ocean API",
    description="API for ocean and weather data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include feature routers
app.include_router(wave_router)
app.include_router(wave_router_v2)
app.include_router(tide_router)
app.include_router(wind_router)
app.include_router(station_router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "time": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5010))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
        workers=1 
    ) 