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
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

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
from features.common.services.model_run_service import ModelRunService

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

        # Initialize cache with Redis from settings
        redis = aioredis.from_url(settings.redis_url)
        FastAPICache.init(RedisBackend(redis), prefix="salty-ocean")
        await init_cache()

        # Initialize services and clients
        model_run_service = ModelRunService()
        station_service = StationService()
        buoy_client = NDBCBuoyClient()
        
        # Initialize wave clients with model run service
        gfs_wave_client = NOAAGFSClient(model_run_service=model_run_service)
        gfs_wave_client_v2 = GFSWaveClient(model_run_service=model_run_service)
        
        gfs_wind_client = GFSWindClient(model_run_service=model_run_service)
        
        # Get current model run and clean up old files
        current_run = await model_run_service.get_latest_available_cycle()
        if current_run:
            gfs_wind_client.file_storage.cleanup_old_files(current_run)
        else:
            logger.warning("No current model run available, skipping file cleanup")
        
        # Store services in app state
        app.state.gfs_client = gfs_wave_client
        app.state.station_service = station_service
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
            wave_service=app.state.wave_service,
            station_service=station_service
        )
        
        # Start GFS Wave V2 initialization in background
        logger.info("Starting GFS Wave V2 dataset initialization...")
        initialization_task = asyncio.create_task(gfs_wave_client_v2.initialize())
        app.state.wave_init_task = initialization_task
        
        # Wait for initialization to complete
        try:
            await initialization_task
            logger.info("GFS Wave V2 initialization completed")
        except Exception as e:
            logger.error(f"GFS Wave V2 initialization failed: {str(e)}")
            # Continue app startup even if initialization fails
            # The service will retry initialization on first request
        
        logger.info("🚀 App started")
        yield
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    finally:
        # Cancel wave initialization if still running
        if hasattr(app.state, "wave_init_task") and not app.state.wave_init_task.done():
            app.state.wave_init_task.cancel()
            try:
                await app.state.wave_init_task
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