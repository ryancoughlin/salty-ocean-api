import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

from features.common.models.model_run_types import ModelRunConfig, ModelRunStatus
from features.common.services.model_run_utils import process_model_cycle
from features.common.services.model_run_service import ModelRunService
from features.waves.services.noaa_gfs_client import NOAAGFSClient
from features.wind.services.gfs_wind_client import GFSWindClient

logger = logging.getLogger(__name__)

async def run_model_task(
    model_run_service: ModelRunService,
    wave_client: NOAAGFSClient,
    wind_client: GFSWindClient,
    config: Optional[ModelRunConfig] = None
) -> None:
    """Run the model processing task."""
    config = config or ModelRunConfig()
    last_processed_cycle = None

    while True:
        try:
            # Get latest available cycle
            cycle_date, cycle_hour = await model_run_service.get_latest_available_cycle()
            cycle_id = f"{cycle_date.strftime('%Y%m%d')}_{cycle_hour}"

            # Skip if already processed
            if cycle_id == last_processed_cycle:
                await asyncio.sleep(config.check_interval_seconds)
                continue

            # Check retry eligibility
            if not model_run_service.should_retry(cycle_date, cycle_hour):
                await asyncio.sleep(config.check_interval_seconds)
                continue

            # Process cycle
            attempt = await process_model_cycle(
                wave_client,
                wind_client,
                cycle_date,
                cycle_hour,
                config
            )

            # Update service status
            model_run_service.track_attempt(
                cycle_date,
                cycle_hour,
                attempt.status,
                attempt.error
            )

            # Update last processed cycle if complete
            if attempt.status == ModelRunStatus.COMPLETE:
                last_processed_cycle = cycle_id
                await asyncio.sleep(config.check_interval_seconds)
            else:
                await asyncio.sleep(config.retry_interval_seconds)

        except Exception as e:
            logger.error(f"Error in model run task: {str(e)}")
            await asyncio.sleep(config.retry_interval_seconds) 