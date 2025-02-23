from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
from features.common.services.model_run_service import ModelRun
from typing import List, Tuple

logger = logging.getLogger(__name__)

class GFSFileStorage:
    """Handles storage and retrieval of GFS GRIB files."""
    
    def __init__(self, base_dir: str = "downloaded_data/gfs_wind"):
        """Initialize the file storage with a base directory."""
        self.base_dir = Path(base_dir)
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_regional_file_path(self, region: str, model_run: ModelRun, forecast_hour: int) -> Path:
        """Generate the path for a regional GFS file."""
        return self.base_dir / f"{region}_gfs_{model_run.date_str}_{model_run.cycle_hour:02d}z_f{forecast_hour:03d}.grib2"
    
    def is_file_valid(self, file_path: Path) -> bool:
        """Check if a file exists."""
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
        model_run: ModelRun,
        forecast_hours: List[int]
    ) -> List[Tuple[int, Path]]:
        """Get list of missing or invalid files for a region."""
        missing = []
        for hour in forecast_hours:
            file_path = self.get_regional_file_path(region, model_run, hour)
            if not self.is_file_valid(file_path):
                missing.append((hour, file_path))
        return missing
    
    def get_valid_files(
        self,
        region: str,
        model_run: ModelRun,
        forecast_hours: List[int]
    ) -> List[Path]:
        """Get list of valid files for a region."""
        valid = []
        for hour in forecast_hours:
            file_path = self.get_regional_file_path(region, model_run, hour)
            if self.is_file_valid(file_path):
                valid.append(file_path)
            return valid
    
    def cleanup_old_files(self, current_run: ModelRun) -> None:
        """Delete files from older model runs."""
        try:
            current_pattern = f"*_{current_run.date_str}_{current_run.cycle_hour:02d}z_*.grib2"
            deleted_count = 0
            
            for file_path in self.base_dir.glob("*.grib2"):
                if current_pattern not in str(file_path):
                    file_path.unlink()
                    deleted_count += 1
                    
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} wind files from previous model runs")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}") 