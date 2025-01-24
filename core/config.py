from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List

class Settings(BaseSettings):
    """Application settings."""
    
    # Storage settings
    data_dir: str = "data"
    
    # NDBC settings
    ndbc_base_url: str = "https://www.ndbc.noaa.gov/data/realtime2/"
    spectral_url: str = "https://www.ndbc.noaa.gov/data/realtime2/"
    
    # NOAA CO-OPS settings
    coops_base_url: str = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    
    # Wave model settings
    base_url: str = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
    model_runs: List[str] = ["00", "06", "12", "18"]
    forecast_hours: List[int] = list(range(0, 385, 3))  # 0 to 384 every 3 hours
    
    models: Dict = {
        "atlantic": {
            "name": "atlocn.0p16",
            "grid": {
                "lat": {
                    "start": 0,
                    "end": 50,
                    "resolution": 0.16,
                    "size": 301
                },
                "lon": {
                    "start": -98,
                    "end": -30,
                    "resolution": 0.16,
                    "size": 425
                }
            }
        },
        "pacific": {
            "name": "paclocn.0p16",
            "grid": {
                "lat": {
                    "start": 0,
                    "end": 60,
                    "resolution": 0.16,
                    "size": 376
                },
                "lon": {
                    "start": -180,
                    "end": -115,
                    "resolution": 0.16,
                    "size": 407
                }
            }
        }
    }
    
    # Development settings
    development: Dict = {
        "enabled": True,
        "force_download": False,
        "max_forecast_hours": 24  # Limit forecast hours in development
    }
    
    # Request settings
    request: Dict = {
        "timeout": 300,  # 5 minutes
        "max_retries": 3,
        "retry_delay": 5  # seconds
    }

    model_config = SettingsConfigDict(
        env_prefix="salty_",
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings() 