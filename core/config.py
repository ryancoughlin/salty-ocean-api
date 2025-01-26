from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Any

class Settings(BaseSettings):
    """Application settings."""
    
    # Storage settings
    data_dir: str = "data"
    
    # Cache settings
    cache: Dict[str, Any] = {
        "enabled": True,
        "backend": "memory",  # Using memory backend
        "prefix": "salty_ocean",
        "ttl": {
            "wave_forecast": 21600,     # 6 hours (until next model run)
            "station_summary": 21600,   # 6 hours (until next model run)
            "ndbc_observations": 1800,  # 30 minutes (NDBC updates at :26 and :56)
            "tide_stations": None,      # No expiration for static station lists
            "tide_predictions": 86400,  # 24 hours for tide predictions
            "stations_geojson": None    # No expiration for static station lists
        }
    }
    
    # NDBC settings
    ndbc_base_url: str = "https://www.ndbc.noaa.gov/data/realtime2/"
    spectral_url: str = "https://www.ndbc.noaa.gov/data/realtime2/"
    
    # NOAA CO-OPS settings
    coops_metadata_url: str = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
    coops_base_url: str = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    coops_params: Dict = {
        "product": "predictions",
        "datum": "MLLW",
        "units": "english",
        "time_zone": "lst_ldt",
        "format": "json"
    }
    
    # Wave model settings
    base_url: str = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
    # NOAA NOMADS runs four times daily at 00, 06, 12, and 18 UTC
    model_runs: List[str] = ["00", "06", "12", "18"]
    # Only download files that contain 3-hourly forecasts (f120 through f384)
    forecast_files: List[int] = list(range(120, 385, 3))  # Files to download: f120, f123, f126, ..., f384
    forecast_hours: List[int] = list(range(120, 385, 3))  # Process 3-hourly data points from these files
    
    models: Dict = {
        "atlantic": {
            "name": "atlocn.0p16",
            "grid": {
                "lat": {
                    "start": 0,
                    "end": 55,
                    "resolution": 0.16,
                    "size": 331
                },
                "lon": {
                    "start": -100,
                    "end": -50,
                    "resolution": 0.16,
                    "size": 301
                }
            }
        },
        # "pacific": {
        #     "name": "paclocn.0p16",
        #     "grid": {
        #         "lat": {
        #             "start": 0,
        #             "end": 60,
        #             "resolution": 0.16,
        #             "size": 376
        #         },
        #         "lon": {
        #             "start": -180,
        #             "end": -115,
        #             "resolution": 0.16,
        #             "size": 407
        #         }
        #     }
        # }
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