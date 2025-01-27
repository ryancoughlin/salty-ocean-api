from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

from core.config import settings
from core.logging_config import setup_logging
from endpoints.tide_stations import router as tide_router
from endpoints.offshore_stations import router as offshore_router
from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from core.cache import init_cache
from services.scheduler_service import SchedulerService

# Setup logging with EST times
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        # Create data directory if it doesn't exist
        Path("data").mkdir(exist_ok=True)
        
        # Initialize cache
        await init_cache()
        
        # Initialize services
        wave_processor = WaveDataProcessor()
        wave_downloader = WaveDataDownloader()
        scheduler = SchedulerService()
        
        # First attempt to download initial data
        logger.info("Downloading initial wave model data...")
        success = await wave_downloader.download_model_data()
        if not success:
            logger.error("Failed to download initial wave model data")
            raise ValueError("No wave model data available - cannot start app")
            
        # Then load the dataset
        logger.info("Loading initial wave model dataset...")
        await wave_processor.preload_dataset()
        logger.info("Initial dataset loaded")
        
        # Start scheduler for future updates
        scheduler.start()
        
        logger.info("App started - services initialized")
        yield
        
        # Cleanup on shutdown
        scheduler.stop()
        logger.info("App shutdown")
        
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise
    finally:
        logger.info("App shutdown")

app = FastAPI(
    title="Wave and Tide Forecast API",
    description="API for accessing wave forecasts, tide predictions, and real-time buoy data",
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

# Include routers
app.include_router(tide_router, prefix="/tide-stations", tags=["tide-stations"])
app.include_router(offshore_router, prefix="/offshore-stations", tags=["offshore-stations"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "scheduler_running": scheduler.scheduler.running,
        "next_runs": {
            "wave_forecasts": scheduler.get_next_run_time("wave_forecasts"),
        }
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
        log_level="info"
    ) 