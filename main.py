from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import asyncio
import signal
import sys

from core.config import settings
from endpoints.tide_stations import router as tide_router
from endpoints.offshore_stations import router as offshore_router
from services.wave_data_processor import WaveDataProcessor
from services.wave_data_downloader import WaveDataDownloader

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="Wave and Tide Forecast API",
        description="API for accessing wave forecasts, tide predictions, and real-time buoy data",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
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

    return app

app = create_application()

# Initialize services
processor = WaveDataProcessor()
downloader = WaveDataDownloader()

# Track background tasks
background_tasks = set()

async def update_model_data():
    """Background task to update model data periodically"""
    try:
        while True:
            try:
                await downloader.cleanup_old_files()
                await downloader.download_model_data()
            except Exception as e:
                logger.error(f"Error updating model data: {str(e)}")
            
            await asyncio.sleep(settings.development["max_forecast_hours"] * 3600)
    except asyncio.CancelledError:
        logger.info("Update model data task cancelled")
        raise

def handle_sigterm(signum, frame):
    """Handle termination signals"""
    logger.info("Received signal to terminate. Cleaning up...")
    
    for task in background_tasks:
        if not task.done():
            logger.info("Cancelling background task...")
            task.cancel()
    
    try:
        loop = asyncio.get_event_loop()
        pending = asyncio.all_tasks(loop=loop)
        loop.run_until_complete(asyncio.gather(*pending))
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
    
    logger.info("Cleanup complete. Exiting...")
    sys.exit(0)

@app.on_event("startup")
async def startup_event():
    """Initialize data and start background tasks on startup"""
    # Ensure data directory exists
    Path(settings.data_dir).mkdir(exist_ok=True)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Start background task for data updates
    task = asyncio.create_task(update_model_data())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down server...")
    handle_sigterm(None, None)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    
    config = uvicorn.Config(
        "main:app",
        host="0.0.0.0",
        port=5010,
        reload=True,
        reload_includes=["*.py"],
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, initiating shutdown...")
        handle_sigterm(None, None) 