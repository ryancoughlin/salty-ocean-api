from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import os
from contextlib import asynccontextmanager
from datetime import datetime

from core.config import settings
from core.logging_config import setup_logging
from core.cache import init_cache

# Feature routes
from features.waves.routes.wave_routes import router as wave_router
from features.tides.routes.tide_routes import router as tide_router
from features.wind.routes.wind_routes import router as wind_router
from features.stations.routes.station_routes import router as station_router

# Wave services and clients
from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.waves.services.wave_data_service import WaveDataService
from features.waves.services.ndbc_buoy_client import NDBCBuoyClient

# Weather services
from features.weather.services.summary_service import WeatherSummaryService
from features.weather.services.gfs_service import GFSForecastManager

# Station services
from features.stations.services.station_service import StationService

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        Path("data").mkdir(exist_ok=True)

        await init_cache()

        # Initialize services and clients
        buoy_client = NDBCBuoyClient()
        station_service = StationService()
        gfs_client = NOAAGFSClient()
        weather_service = WeatherSummaryService()
        gfs_manager = GFSForecastManager()
        
        # Store service instances in app state
        app.state.weather_service = weather_service
        app.state.gfs_manager = gfs_manager
        app.state.gfs_client = gfs_client
        app.state.station_service = station_service
        
        # Initialize feature services
        app.state.wave_service = WaveDataService(
            gfs_client=gfs_client,
            weather_service=weather_service,
            buoy_client=buoy_client,
            station_service=station_service
        )
        
        # Initial data load
        try:
            # Initialize GFS data
            logger.info("Initializing GFS forecast data...")
            await gfs_manager.initialize()
            logger.info("GFS forecast data initialized successfully")

            logger.info("🚀 App started")
            yield
            
        except Exception as e:
            logger.error(f"Error during data initialization: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    finally:
        logger.info("Shutting down application...")
        
        # Stop the scheduler
        if hasattr(app.state, "scheduler"):
            await app.state.scheduler.stop()
            
        # Clear GFS forecast data
        if hasattr(app.state, "gfs_manager"):
            app.state.gfs_manager.forecast = None
            app.state.gfs_manager.last_update = None
            logger.info("GFS forecast data cleared")
            
        # Close GFS wave service
        if hasattr(app.state, "gfs_wave_service"):
            await app.state.gfs_wave_service.close()
            
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
        "scheduler_running": app.state.scheduler._task is not None and not app.state.scheduler._task.done(),
        "time": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5010))
    
    # Development mode uses Uvicorn with reload
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  # Always reload in direct execution
        log_level="info",
        workers=1  # Single worker for development
    ) 