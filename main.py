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

# Wave services
from features.waves.services.wave_data_processor import WaveDataProcessor
from features.waves.services.wave_data_downloader import WaveDataDownloader
from features.waves.services.scheduler_service import SchedulerService
from features.waves.services.prefetch_service import PrefetchService
from features.waves.services.wave_service import WaveService
from features.waves.services.buoy_service import BuoyService

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

        # Initialize services
        # wave_processor = WaveDataProcessor()
        # wave_downloader = WaveDataDownloader()
        buoy_service = BuoyService()
        station_service = StationService()
        prefetch_service = PrefetchService(wave_processor=wave_processor, buoy_service=buoy_service)
        weather_service = WeatherSummaryService()
        gfs_manager = GFSForecastManager()
        scheduler = SchedulerService(
            # wave_processor=wave_processor,
            # wave_downloader=wave_downloader,
            prefetch_service=prefetch_service,
            gfs_manager=gfs_manager
        )
        
        # Store service instances in app state
        # app.state.wave_processor = wave_processor
        # app.state.wave_downloader = wave_downloader
        app.state.prefetch_service = prefetch_service
        app.state.weather_service = weather_service
        app.state.gfs_manager = gfs_manager
        app.state.scheduler = scheduler
        app.state.station_service = station_service
        
        # Initialize feature services
        app.state.wave_service = WaveService(
            prefetch_service=prefetch_service,
            weather_service=weather_service,
            buoy_service=buoy_service,
            station_service=station_service
        )
        
        # Initial data load
        try:
            # Initialize GFS data
            logger.info("Initializing GFS forecast data...")
            await gfs_manager.initialize()
            logger.info("GFS forecast data initialized successfully")
            
            # Initialize wave model data
            logger.info("Checking wave model data...")
            if await wave_downloader.download_latest():
                logger.info("New wave model data downloaded")
            else:
                logger.info("Using existing wave model data")
        
            # Load the data
            logger.info("Loading wave model data...")
            if wave_processor.get_dataset() is not None:
                logger.info("Wave model data loaded successfully")
                
                # Prefetch forecast data
                logger.info("Prefetching forecast data...")
                await prefetch_service.prefetch_all()
                logger.info("Forecast data prefetched successfully")
            else:
                logger.error("Failed to load wave model data")
                raise HTTPException(status_code=500, detail="Failed to load wave model data")
        
            # Start scheduler for future updates
            logger.info("Starting scheduler...")
            await scheduler.start()
        
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
            
        # Clear wave model data
        if hasattr(app.state, "wave_processor"):
            app.state.wave_processor.close_dataset()
        if hasattr(app.state, 'wave_downloader'):
            await app.state.wave_downloader.close()
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