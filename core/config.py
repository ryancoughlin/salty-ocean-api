from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone

class Settings(BaseSettings):
    """Application settings."""
    
    data_dir: str = "data"

    cache: Dict[str, Any] = {
        "enabled": True,
        "backend": "memory",
        "prefix": "salty_ocean"
    }
    
    ndbc_base_url: str = "https://www.ndbc.noaa.gov/data/realtime2/"

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
    # Download files every hour from f000 to f120
    forecast_files: List[int] = list(range(0, 121, 1))  # Files to download: f000, f001, f002, ..., f120
    forecast_hours: List[int] = list(range(0, 121, 1))  # Process hourly data points
    
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
    
    request: Dict = {
        "timeout": 300,
        "max_retries": 3,
        "retry_delay": 5000
    }

    def get_cache_ttl(self) -> Dict[str, int]:
        """Get cache TTL values. Cache is flushed when new model data is available."""
        return {
            "wave_forecast": 14400,     # 4 hours (max time between model runs)
            "station_summary": 1800,    # 30 minutes (match NDBC observation frequency)
            "ndbc_observations": 1800,  # 30 minutes (NDBC updates at :26 and :56)
            "tide_stations": None,      # No expiration for static station lists
            "tide_predictions": 86400,  # 24 hours for tide predictions
            "stations_geojson": None    # No expiration for static station lists
        }

    model_config = SettingsConfigDict(
        env_prefix="salty_",
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings() 