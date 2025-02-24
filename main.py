from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import os
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
from typing import Dict, Optional

from core.config import settings
from core.logging_config import setup_logging

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
from features.wind.services.wind_data_service import WindDataService
from features.wind.services.gfs_wind_client import GFSWindClient
from features.common.services.model_run_service import ModelRunService
from features.tides.services.tide_service import TideService
from features.common.model_run import ModelRun

setup_logging()
logger = logging.getLogger(__name__)

class ModelRunState:
    """Class to manage model run state and clients."""
    def __init__(self):
        self.current_model_run: Optional[ModelRun] = None
        self.gfs_client = None
        self.gfs_wave_client_v2 = None
        self.gfs_wind_client = None
        
    async def initialize(self, model_run: ModelRun):
        """Initialize clients with model run."""
        self.current_model_run = model_run
        self.gfs_client = NOAAGFSClient(model_run=model_run)
        self.gfs_wave_client_v2 = GFSWaveClient(model_run=model_run)
        self.gfs_wind_client = GFSWindClient(model_run=model_run)
        
        # Initialize wave and wind data
        await self.gfs_wave_client_v2.initialize()
        await self.gfs_wind_client.initialize()
        
    async def cleanup(self):
        """Cleanup clients."""
        if self.gfs_wave_client_v2:
            await self.gfs_wave_client_v2.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        logger.info("🚀 Starting Salty Ocean API...")
    
        Path("downloaded_data/gfs_wave").mkdir(exist_ok=True)
        Path("downloaded_data/gfs_wind").mkdir(exist_ok=True)

        # Initialize model run service and get latest cycle
        logger.info("\n📅 Initializing model run service...")
        model_run_service = ModelRunService()
        current_model_run = await model_run_service.get_latest_available_cycle()
        if not current_model_run:
            logger.error("❌ Failed to get initial model run")
            raise Exception("Failed to get initial model run")
            
        # Initialize active model run state
        active_state = ModelRunState()
        await active_state.initialize(current_model_run)
        
        # Store services in app state
        app.state.model_run_service = model_run_service
        app.state.active_state = active_state
        app.state.prefetch_state = None  # Will hold prefetched state
            
        # Initialize services
        station_service = StationService()
        buoy_client = NDBCBuoyClient()
        
        # Ensure clients are initialized before creating services
        if not active_state.gfs_client or not active_state.gfs_wave_client_v2 or not active_state.gfs_wind_client:
            logger.error("❌ Failed to initialize one or more clients")
            raise Exception("Failed to initialize clients")
            
        # Store other services in app state
        app.state.station_service = station_service
        app.state.tide_service = TideService()
        app.state.wave_service = WaveDataService(
            gfs_client=active_state.gfs_client,
            buoy_client=buoy_client,
            station_service=station_service
        )
        app.state.wave_service_v2 = WaveDataServiceV2(
            gfs_client=active_state.gfs_wave_client_v2,
            buoy_client=buoy_client,
            station_service=station_service
        )
        app.state.wind_service = WindDataService(
            gfs_client=active_state.gfs_wind_client,
            station_service=station_service
        )
        app.state.condition_summary_service = ConditionSummaryService(
            wind_service=app.state.wind_service,
            wave_service=app.state.wave_service_v2,
            station_service=station_service
        )
        
        async def prefetch_new_model_run(new_model_run: ModelRun):
            """Prefetch data for new model run in background."""
            try:
                logger.info(f"🔄 Prefetching data for new model run {new_model_run.date_str} {new_model_run.cycle_hour:02d}Z")
                new_state = ModelRunState()
                await new_state.initialize(new_model_run)
                return new_state
            except Exception as e:
                logger.error(f"❌ Error prefetching new model run: {str(e)}")
                return None
                
        async def switch_model_run(new_state: ModelRunState):
            """Switch to new model run state."""
            try:
                old_state = app.state.active_state
                
                # Update services with new clients
                app.state.wave_service.gfs_client = new_state.gfs_client
                app.state.wave_service_v2.gfs_client = new_state.gfs_wave_client_v2
                app.state.wind_service.gfs_client = new_state.gfs_wind_client
                
                # Switch active state
                app.state.active_state = new_state
                
                # Cleanup old state
                await old_state.cleanup()
                logger.info("✅ Successfully switched to new model run")
                
            except Exception as e:
                logger.error(f"❌ Error switching model run: {str(e)}")
        
        # Task to check for new model runs
        async def check_model_runs():
            while True:
                try:
                    new_model_run = await model_run_service.get_latest_available_cycle()
                    current_run = app.state.active_state.current_model_run
                    
                    # Use the simplified comparison method
                    if new_model_run and model_run_service.is_newer_run(new_model_run, current_run):
                        # Start prefetching if not already in progress
                        if not app.state.prefetch_state:
                            logger.info("🔄 New model run detected, starting prefetch...")
                            app.state.prefetch_state = await prefetch_new_model_run(new_model_run)
                            
                            if app.state.prefetch_state:
                                # Switch to new model run
                                await switch_model_run(app.state.prefetch_state)
                                app.state.prefetch_state = None
                                
                except Exception as e:
                    logger.error(f"❌ Error checking for new model run: {str(e)}")
                finally:
                    # Check every 15 minutes
                    await asyncio.sleep(900)
                    
        # Start model run check task
        app.state.model_run_task = asyncio.create_task(check_model_runs())
        
        logger.info("\n✨ API startup complete - ready to serve requests")
        yield
            
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")
        raise
    finally:
        logger.info("\n🔄 Shutting down API...")
        # Cancel all background tasks
        if hasattr(app.state, "model_run_task"):
            app.state.model_run_task.cancel()
            try:
                await app.state.model_run_task
            except asyncio.CancelledError:
                pass
            
        # Cleanup active state
        if hasattr(app.state, "active_state"):
            await app.state.active_state.cleanup()
            
        # Cleanup prefetch state if exists
        if hasattr(app.state, "prefetch_state") and app.state.prefetch_state:
            await app.state.prefetch_state.cleanup()
            
        logger.info("👋 API shutdown complete")

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