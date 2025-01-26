from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

from core.config import settings
from endpoints.tide_stations import router as tide_router
from endpoints.offshore_stations import router as offshore_router
from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader
from core.cache import init_cache
from services.scheduler_service import SchedulerService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track background tasks
background_tasks = set()

# Initialize services
wave_processor = WaveDataProcessor()
wave_downloader = WaveDataDownloader()
scheduler = SchedulerService()

async def update_model_data():
    """Background task to update model data periodically"""
    while True:
        try:
            logger.info("Starting model data update")
            
            try:
                success = await wave_downloader.download_model_data()
                if success:
                    logger.info("Successfully updated model data")
                else:
                    logger.warning("Failed to update model data, will retry later")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error updating model data: {str(e)}")
            
            try:
                # Calculate time until next model run
                current_hour = datetime.utcnow().hour
                model_runs = sorted(map(int, settings.model_runs))
                
                # Find next model run
                next_run = next((run for run in model_runs if run > current_hour), model_runs[0])
                
                # Calculate sleep time (add 1 hour buffer for data availability)
                sleep_hours = next_run - current_hour if next_run > current_hour else (24 - current_hour + next_run)
                sleep_seconds = (sleep_hours + 1) * 3600  # Add 1 hour buffer
                
                logger.info(f"Sleeping until next model run at {next_run:02d}z (approximately {sleep_hours + 1:.1f} hours)")
                await asyncio.sleep(min(sleep_seconds, settings.development["max_forecast_hours"] * 3600))
            except asyncio.CancelledError:
                logger.info("Update model data task cancelled during sleep")
                break
        except asyncio.CancelledError:
            logger.info("Update model data task cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in update task: {str(e)}")
            try:
                await asyncio.sleep(300)  # 5 minutes
            except asyncio.CancelledError:
                break

async def cleanup():
    """Cleanup background tasks"""
    logger.info("Starting cleanup...")
    
    # Cancel all background tasks
    tasks = [t for t in background_tasks if not t.done()]
    if tasks:
        logger.info(f"Cancelling {len(tasks)} background tasks")
        for task in tasks:
            task.cancel()
        
        try:
            # Wait for tasks to finish with a timeout
            await asyncio.wait(tasks, timeout=5.0)
            # Clean up any remaining tasks
            for task in tasks:
                if not task.done():
                    logger.warning(f"Task {task} did not complete in time")
        except Exception as e:
            logger.error(f"Error during task cleanup: {str(e)}")
    
    # Stop scheduler
    scheduler.stop()
    logger.info("Cleanup complete")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    try:
        # Ensure data directory exists
        Path(settings.data_dir).mkdir(exist_ok=True)
        
        # Initialize cache
        await init_cache()
        
        # Start background task for model data updates
        update_task = asyncio.create_task(update_model_data())
        background_tasks.add(update_task)
        
        # Initial data load
        logger.info("Starting initial data load")
        await wave_processor.preload_dataset()
        logger.info("Initial data load complete")
        
        # Start scheduler for future updates
        scheduler.start()
        
        logger.info("Application startup complete")
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Application shutdown initiated")
        await cleanup()
        logger.info("Application shutdown complete")

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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    tide_router,
    prefix="/tide-stations",
    tags=["tide-stations"]
)
app.include_router(
    offshore_router,
    prefix="/offshore-stations",
    tags=["offshore-stations"]
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "scheduler_running": scheduler.scheduler.running,
        "background_tasks": len(background_tasks),
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