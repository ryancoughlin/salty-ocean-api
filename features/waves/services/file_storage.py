from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
from features.common.services.model_run_service import ModelRun

logger = logging.getLogger(__name__)

class GFSWaveFileStorage:
    """Handles storage and retrieval of GFS Wave GRIB files."""
    
    def __init__(self, base_dir: str = "cache/gfs_wave"):
        """Initialize the file storage with a base directory."""
        self.base_dir = Path(base_dir)
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_file_path(self, region: str, cycle_date: datetime, cycle_hour: str, forecast_hour: int) -> Path:
        """Generate the path for a GFS wave file."""
        return self.base_dir / f"{region}_gfs_{cycle_date.strftime('%Y%m%d')}_{cycle_hour}z_f{forecast_hour:03d}.grib2"
    
    def is_file_valid(self, file_path: Path) -> bool:
        """Check if a file exists and matches current model run pattern."""
        return file_path.exists()
    
    async def save_file(self, file_path: Path, content: bytes) -> bool:
        """Save file content to storage."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {str(e)}")
            return False
    
    def get_missing_files(
        self,
        region: str,
        cycle_date: datetime,
        cycle_hour: str,
        forecast_hours: list[int]
    ) -> list[tuple[int, Path]]:
        """Get list of forecast hours and paths for missing or invalid files."""
        missing = []
        for fh in forecast_hours:
            file_path = self.get_file_path(region, cycle_date, cycle_hour, fh)
            if not self.is_file_valid(file_path):
                missing.append((fh, file_path))
        return missing
    
    def get_valid_files(
        self,
        region: str,
        cycle_date: datetime,
        cycle_hour: str,
        forecast_hours: list[int]
    ) -> list[Path]:
        """Get list of all valid files for a cycle."""
        return [
            self.get_file_path(region, cycle_date, cycle_hour, fh)
            for fh in forecast_hours
            if self.is_file_valid(
                self.get_file_path(region, cycle_date, cycle_hour, fh)
            )
        ]
    
    def cleanup_old_files(self, current_run: ModelRun) -> None:
        """Delete files from older model runs."""
        try:
            current_pattern = f"*_{current_run.run_date.strftime('%Y%m%d')}_{current_run.cycle_hour:02d}z_*.grib2"
            deleted_count = 0
            
            for file_path in self.base_dir.glob("*.grib2"):
                # Keep files matching current model run pattern
                if current_pattern not in str(file_path):
                    file_path.unlink()
                    deleted_count += 1
                    
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} wave files from previous model runs")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}") 