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

# Feature routes
from features.waves.routes.wave_routes import router as wave_router
from features.tides.routes.tide_routes import router as tide_router
from features.wind.routes.wind_routes import router as wind_router
from features.stations.routes.station_routes import router as station_router

# Services and clients
from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.waves.services.wave_data_service import WaveDataService
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient
from features.stations.services.station_service import StationService
from features.stations.services.condition_summary_service import ConditionSummaryService
from features.wind.services.wind_service import WindService
from features.wind.services.gfs_wind_client import GFSWindClient
from features.common.services.model_run_service import ModelRunService
from features.common.services.model_run_task import run_model_task
from features.common.services.prefetch_service import PrefetchService

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        # Create required directories
        Path("data").mkdir(exist_ok=True)
        Path("downloaded_data").mkdir(exist_ok=True)

        # Initialize cache
        await init_cache()

        # Initialize services and clients
        model_run_service = ModelRunService()
        station_service = StationService()
        buoy_client = NDBCBuoyClient()
        gfs_wave_client = NOAAGFSClient(model_run_service=model_run_service)
        gfs_wind_client = GFSWindClient(model_run_service=model_run_service)
        
        # Clean up old downloaded files
        gfs_wind_client.file_storage.cleanup_old_files(max_age_hours=24)
        
        app.state.gfs_client = gfs_wave_client
        app.state.station_service = station_service
        
        # Initialize feature services
        app.state.wave_service = WaveDataService(
            gfs_client=gfs_wave_client,
            buoy_client=buoy_client,
            station_service=station_service
        )
        
        app.state.wind_service = WindService(
            gfs_client=gfs_wind_client,
            station_service=station_service
        )

        # Initialize condition summary service
        app.state.condition_summary_service = ConditionSummaryService(
            wind_service=app.state.wind_service,
            wave_service=app.state.wave_service,
            station_service=station_service
        )
        
        # Initialize prefetch service
        prefetch_service = PrefetchService(
            station_service=station_service,
            wave_service=app.state.wave_service,
            wind_service=app.state.wind_service,
            batch_size=5,  # Process 5 stations at a time
            requests_per_minute=15  # Conservative rate limit (1 request every 4 seconds)
        )
        app.state.prefetch_service = prefetch_service
        
        # Initialize model run task with prefetch service
        model_run_task = asyncio.create_task(
            run_model_task(
                model_run_service=model_run_service,
                prefetch_service=prefetch_service,
                wave_client=gfs_wave_client,
                wind_client=gfs_wind_client
            )
        )
        app.state.model_run_task = model_run_task
        
        # Start initial pre-fetch in background
        prefetch_task = prefetch_service.start_background_prefetch()
        app.state.prefetch_task = prefetch_task
        
        logger.info("🚀 App started")
        yield
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    finally:
        # Cancel and cleanup background tasks
        if hasattr(app.state, "model_run_task"):
            app.state.model_run_task.cancel()
            try:
                await app.state.model_run_task
            except asyncio.CancelledError:
                pass
                
        if hasattr(app.state, "prefetch_service"):
            await app.state.prefetch_service.cleanup()
            
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