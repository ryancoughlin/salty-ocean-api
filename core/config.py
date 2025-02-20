from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone

class Settings(BaseSettings):
    """Application settings."""
    
    # GFS Wave Bulletin settings
    gfs_wave_base_url: str = "https://nomads.ncep.noaa.gov"
    gfs_wave_cycles: List[str] = ["00", "06", "12", "18"]
    gfs_wave_bulletin_path: str = "wave/station/bulls.t{hour}z/gfswave.{station_id}.bull"
    
    # Data directory
    data_dir: str = "data"
    cache_dir: str = "cache"  # Directory for GRIB file caching

    cache: Dict[str, Any] = {
        "enabled": True,
        "backend": "memory",
        "prefix": "salty_ocean"
    }
    
    # NDBC settings
    ndbc_base_url: str = "https://www.ndbc.noaa.gov/data/realtime2/"
    ndbc_data_types: Dict[str, str] = {
        "std": "txt",           # Standard meteorological data
        "spec": "spec",         # Spectral wave summary
        "data_spec": "data_spec", # Raw spectral wave data
        "swdir": "swdir",       # Spectral wave direction (alpha1)
        "swdir2": "swdir2",     # Spectral wave direction (alpha2)
        "swr1": "swr1",         # Spectral wave data (r1)
        "swr2": "swr2"          # Spectral wave data (r2)
    }

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
    forecast_hours: int = 120  # Maximum forecast hours to process
    
    models: Dict = {
        "atlantic": {
            "name": "atlocn.0p16",
            "grid": {
                "lat": {
                    "start": 0,
                    "end": 55.00011,
                    "resolution": 0.167,
                    "points": 331
                },
                "lon": {
                    "start": 260,  # -100 degrees in 360-notation
                    "end": 310.00010,  # -50 degrees in 360-notation
                    "resolution": 0.167,
                    "points": 301
                }
            },
            "variables": {
                "wave": {
                    "dirpw": "surface primary wave direction [deg]",
                    "htsgw": "surface significant height of combined wind waves and swell [m]",
                    "perpw": "surface primary wave mean period [s]"
                },
                "swell": {
                    "swdir_1": "1 in sequence direction of swell waves [deg]",
                    "swdir_2": "2 in sequence direction of swell waves [deg]",
                    "swdir_3": "3 in sequence direction of swell waves [deg]",
                    "swell_1": "1 in sequence significant height of swell waves [m]",
                    "swell_2": "2 in sequence significant height of swell waves [m]",
                    "swell_3": "3 in sequence significant height of swell waves [m]",
                    "swper_1": "1 in sequence mean period of swell waves [s]",
                    "swper_2": "2 in sequence mean period of swell waves [s]",
                    "swper_3": "3 in sequence mean period of swell waves [s]"
                },
                "wind": {
                    "ugrd": "surface u-component of wind [m/s]",
                    "vgrd": "surface v-component of wind [m/s]",
                    "wdir": "surface wind direction (from which blowing) [degtrue]",
                    "wind": "surface wind speed [m/s]"
                },
                "wind_waves": {
                    "wvdir": "surface direction of wind waves [deg]",
                    "wvhgt": "surface significant height of wind waves [m]",
                    "wvper": "surface mean period of wind waves [s]"
                }
            },
            "forecast": {
                "steps": 129,  # Number of forecast time steps
                "interval": 0.125  # Time step interval in days (3 hours)
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
            "wind_forecast": 14400,     # 4 hours (max time between model runs)
            "wind_data": 14400,         # 4 hours (max time between model runs)
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