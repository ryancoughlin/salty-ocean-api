from datetime import datetime, timezone
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class GFSFileStorage:
    """Handles storage and retrieval of GFS GRIB files."""
    
    def __init__(self, base_dir: str = "downloaded_data/gfs"):
        """Initialize the file storage with a base directory."""
        self.base_dir = Path(base_dir)
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_file_path(self, station_id: str, date: datetime, cycle: str, forecast_hour: int) -> Path:
        """Generate the path for a GFS file."""
        date_str = date.strftime('%Y%m%d')
        return self.base_dir / f"gfs_wind_{station_id}_{date_str}_{cycle}z_f{forecast_hour:03d}.grib2"
    
    def is_file_valid(self, file_path: Path, max_age_hours: int = 6) -> bool:
        """Check if a file exists and is not too old."""
        if not file_path.exists():
            return False
            
        file_age = datetime.now(timezone.utc) - datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
        return file_age.total_seconds() < max_age_hours * 3600
    
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
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> None:
        """Remove files older than specified age."""
        try:
            current_time = datetime.now(timezone.utc)
            for file_path in self.base_dir.glob("*.grib2"):
                file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
                if file_age.total_seconds() > max_age_hours * 3600:
                    file_path.unlink()
                    logger.info(f"Removed old file: {file_path}")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}") 