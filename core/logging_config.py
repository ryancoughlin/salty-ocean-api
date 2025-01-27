import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

class ESTFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        # Convert UTC to EST
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        est = dt.astimezone(timezone(-timedelta(hours=5)))  # EST is UTC-5
        return est.strftime("%Y-%m-%d %H:%M:%S EST")
        
    def format(self, record: logging.LogRecord) -> str:
        # Extract just the filename from the path
        record.name = record.name.split('.')[-1]
        return super().format(record)

def setup_logging() -> None:
    # Create custom formatter
    formatter = ESTFormatter(
        fmt="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S EST"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Remove existing handlers and add our custom handler
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING) 