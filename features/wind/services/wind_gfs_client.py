import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from fastapi import HTTPException
import numpy as np

from features.wind.models.wind_types import WindData, WindForecastResponse
from features.common.models.station_types import StationInfo, Location
from features.weather.services.gfs_service import GFSForecastManager

logger = logging.getLogger(__name__)

class WindGFSClient:
    """Client for fetching wind data from GFS."""
    
    def __init__(self, gfs_manager: GFSForecastManager):
        self.gfs_manager = gfs_manager
        
    def _calculate_wind(self, u: float, v: float) -> tuple[float, float]:
        """Calculate wind speed and direction from U and V components."""
        try:
            speed = round((u * u + v * v) ** 0.5, 2)
            direction = round((270 - (180 / 3.14159) * (v > 0) * 3.14159 + (180 / 3.14159) * (v < 0) * 3.14159) % 360, 2)
            return speed, direction
        except Exception as e:
            logger.error(f"Error calculating wind: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error calculating wind data: {str(e)}"
            )
            
    def _get_grid_indices(self, lat: float, lon: float, grid_data: Dict) -> Tuple[int, int]:
        """Find the nearest grid point indices for a given lat/lon."""
        try:
            # Get grid coordinates
            grid_lats = grid_data['latitude']
            grid_lons = grid_data['longitude']
            
            # Find nearest points
            lat_idx = np.abs(grid_lats - lat).argmin()
            lon_idx = np.abs(grid_lons - lon).argmin()
            
            return lat_idx, lon_idx
        except Exception as e:
            logger.error(f"Error finding grid indices: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing grid data: {str(e)}"
            )
            
    def get_station_wind_data(self, station_id: str, station_info: Dict) -> WindData:
        """Get current wind conditions for a station."""
        if not self.gfs_manager.forecast:
            raise HTTPException(
                status_code=503,
                detail="Forecast data not available"
            )
            
        try:
            lat = station_info["location"]["coordinates"][1]
            lon = station_info["location"]["coordinates"][0]
            current_time = datetime.now(timezone.utc)
            
            # Get a small grid around the point (0.5 degree buffer)
            lat_min, lat_max = lat - 0.25, lat + 0.25
            lon_min, lon_max = lon - 0.25, lon + 0.25
            
            # Get wind data from GFS for the grid
            result = self.gfs_manager.forecast.get(
                ["ugrd10m", "vgrd10m", "gustsfc"],
                current_time.strftime("%Y%m%d %H:%M"),
                [lat_min, lat_max],
                [lon_min, lon_max]
            )
            
            # Find nearest grid point
            lat_idx, lon_idx = self._get_grid_indices(lat, lon, result)
            
            # Extract values from the response
            u = float(result.variables["ugrd10m"].data[0][lat_idx][lon_idx])
            v = float(result.variables["vgrd10m"].data[0][lat_idx][lon_idx])
            gust = round(float(result.variables["gustsfc"].data[0][lat_idx][lon_idx]), 2)
            
            # Calculate wind speed and direction
            speed, direction = self._calculate_wind(u, v)
            
            return WindData(
                timestamp=current_time,
                wind_speed=speed,
                wind_gust=gust,
                wind_direction=direction
            )
            
        except Exception as e:
            logger.error(f"Error getting wind data for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind data: {str(e)}"
            )
            
    def get_station_wind_forecast(self, station_id: str, station_info: Dict) -> WindForecastResponse:
        """Get 7-day wind forecast for a station."""
        if not self.gfs_manager.forecast:
            raise HTTPException(
                status_code=503,
                detail="Forecast data not available"
            )
            
        try:
            lat = station_info["location"]["coordinates"][1]
            lon = station_info["location"]["coordinates"][0]
            current_time = datetime.now(timezone.utc)
            
            # Get a small grid around the point (0.5 degree buffer)
            lat_min, lat_max = lat - 0.25, lat + 0.25
            lon_min, lon_max = lon - 0.25, lon + 0.25
            
            # Calculate forecast times
            forecast_times = [
                (current_time + timedelta(hours=i)).strftime("%Y%m%d %H:%M")
                for i in range(0, 169, 3)  # 0 to 168 hours (7 days) in 3-hour steps
            ]
            
            # Get all forecast data at once for the grid
            result = self.gfs_manager.forecast.get(
                ["ugrd10m", "vgrd10m", "gustsfc"],
                forecast_times,  # List of times
                [lat_min, lat_max],  # Latitude bounds
                [lon_min, lon_max],  # Longitude bounds
            )
            
            # Find nearest grid point
            lat_idx, lon_idx = self._get_grid_indices(lat, lon, result)
            
            forecasts = []
            for i, forecast_time in enumerate(forecast_times):
                try:
                    # Extract values for this time step
                    u = float(result.variables["ugrd10m"].data[i][lat_idx][lon_idx])
                    v = float(result.variables["vgrd10m"].data[i][lat_idx][lon_idx])
                    gust = round(float(result.variables["gustsfc"].data[i][lat_idx][lon_idx]), 2)
                    
                    # Calculate wind speed and direction
                    speed, direction = self._calculate_wind(u, v)
                    
                    forecasts.append(WindData(
                        timestamp=datetime.strptime(forecast_time, "%Y%m%d %H:%M").replace(tzinfo=timezone.utc),
                        wind_speed=speed,
                        wind_gust=gust,
                        wind_direction=direction
                    ))
                except Exception as e:
                    logger.warning(f"Error processing forecast at time {forecast_time}: {str(e)}")
                    continue
            
            if not forecasts:
                raise HTTPException(
                    status_code=503,
                    detail="No forecast data available"
                )
            
            logger.info(f"Processed {len(forecasts)} forecasts for station {station_id}")
            
            # Create station info model with location
            station = StationInfo(
                id=station_id,
                name=station_info["name"],
                location=Location(
                    type="Point",
                    coordinates=[lon, lat]  # GeoJSON is [longitude, latitude]
                )
            )
            
            return WindForecastResponse(
                station=station,
                forecasts=forecasts
            )
            
        except Exception as e:
            logger.error(f"Error getting wind forecast for station {station_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing wind forecast: {str(e)}"
            ) 