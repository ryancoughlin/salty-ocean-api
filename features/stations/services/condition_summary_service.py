import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from fastapi import HTTPException
from aiocache import cached, SimpleMemoryCache

from features.wind.models.wind_categories import WindDirection, TrendType
from features.waves.models.wave_categories import Conditions
from features.wind.services.wind_data_service import WindDataService
from features.waves.services.wave_data_service_v2 import WaveDataServiceV2
from features.stations.services.station_service import StationService
from features.common.models.station_types import Station
from features.stations.models.summary_types import ConditionSummaryResponse
from features.common.services.cache_config import (
    CURRENT_CONDITIONS_EXPIRE,
    feature_cache_key_builder,
    get_cache
)
from core.config import settings

logger = logging.getLogger(__name__)

class ConditionSummaryService:
    # Default configuration values
    DEFAULT_TREND_THRESHOLD = 10  # Percent change to consider a trend
    DEFAULT_FORECAST_HOURS = 6    # Hours ahead to check for trend
    
    def __init__(
        self,
        wind_service: WindDataService,
        wave_service: WaveDataServiceV2,
        station_service: StationService
    ):
        self.wind_service = wind_service
        self.wave_service = wave_service
        self.station_service = station_service
        self._cache = get_cache()
        
        # Load configuration or use defaults
        self.trend_threshold = getattr(settings, 'trend_threshold_percent', self.DEFAULT_TREND_THRESHOLD)
        self.forecast_hours = getattr(settings, 'trend_forecast_hours', self.DEFAULT_FORECAST_HOURS)
        
        # Load coast direction configuration or use defaults
        self.coast_config = getattr(settings, 'coast_direction', {
            'east_coast': {'min_lon': -100, 'max_lon': -60},
            'west_coast': {'min_lon': -180, 'max_lon': -100}
        })
        
        logger.info(f"Condition summary service initialized with trend threshold {self.trend_threshold}% "
                   f"and forecast window {self.forecast_hours} hours")

    @cached(
        ttl=CURRENT_CONDITIONS_EXPIRE,
        key_builder=feature_cache_key_builder,
        namespace="condition_summary",
        cache=SimpleMemoryCache,
        noself=True
    )
    async def get_station_condition_summary(self, station_id: str) -> ConditionSummaryResponse:
        """Generate a human-readable summary of current conditions and trends."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

            # Get forecasts from the services instead of GFS clients
            wind_forecast = await self.wind_service.get_station_forecast(station_id)
            wave_forecast = await self.wave_service.get_station_forecast(station_id)

            if not wind_forecast or not wind_forecast.forecasts:
                raise HTTPException(status_code=503, detail="Unable to fetch wind conditions")

            if not wave_forecast or not wave_forecast.forecasts:
                raise HTTPException(status_code=503, detail="Unable to fetch wave conditions")

            # Get current conditions with null safety
            current_wave = wave_forecast.forecasts[0] if wave_forecast.forecasts else None
            current_wind = wind_forecast.forecasts[0] if wind_forecast.forecasts else None
            
            if not current_wave or not current_wind:
                raise HTTPException(status_code=503, detail="No current conditions available")

            # Get conditions in configured hours ahead
            future_time = datetime.now(current_wave.time.tzinfo) + timedelta(hours=self.forecast_hours)
            
            # Find future wind forecast point
            future_wind = None
            for forecast in wind_forecast.forecasts:
                if forecast.time >= future_time:
                    future_wind = forecast
                    break
            
            # If no future point found, use the last available
            if not future_wind and wind_forecast.forecasts:
                future_wind = wind_forecast.forecasts[-1]
                
            # Find future wave forecast point
            future_wave = None
            for forecast in wave_forecast.forecasts:
                if forecast.time >= future_time:
                    future_wave = forecast
                    break
                    
            # If no future point found, use the last available
            if not future_wave and wave_forecast.forecasts:
                future_wave = wave_forecast.forecasts[-1]
                
            if not future_wind or not future_wave:
                raise HTTPException(status_code=503, detail="Unable to fetch future conditions")

            # Calculate categories with null safety
            wind_dir = WindDirection.from_degrees(current_wind.direction or 0.0)
            
            # Safe access to wave direction
            wave_direction = current_wave.direction if current_wave.direction is not None else 0.0
            
            conditions = Conditions.from_wind_wave(
                current_wind.speed or 0.0,
                current_wind.direction or 0.0,
                wave_direction
            )

            # Get trends with null safety
            wind_trend = self._get_trend_description(
                current_wind.speed or 0.0, 
                future_wind.speed or 0.0
            )
            
            wave_height_current = current_wave.height if current_wave.height is not None else 0.0
            wave_height_future = future_wave.height if future_wave.height is not None else 0.0
            
            wave_trend = self._get_trend_description(
                wave_height_current,
                wave_height_future
            )
            
            wind_quality = self._get_coast_wind_quality(wind_dir, station)

            # Build summary with null safety
            wave_height = wave_height_current
            wave_period = current_wave.period if current_wave.period is not None else 0.0
            
            wave_desc = f"{wave_height:.1f}ft"
            if wave_period > 0:
                wave_desc += f" {wave_period:.0f}s"
            wave_desc += " waves"
            if wave_trend.value.lower() != "steady":
                wave_desc += f" are {wave_trend.value.lower()}"

            wind_speed = current_wind.speed or 0.0
            wind_desc = f"winds are {wind_speed:.0f}mph {wind_quality} from the {wind_dir.description.lower()}"
            if wind_trend.value.lower() != "steady":
                wind_desc += f" and {wind_trend.value.lower()}"

            summary = f"{wave_desc}, {wind_desc}, making for {conditions.value.lower()} conditions."

            # Create response with structured data
            return ConditionSummaryResponse(
                station=station,
                summary=summary,
                generated_at=datetime.now(current_wave.time.tzinfo),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating condition summary: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def _get_trend_description(self, current: float, future: float) -> TrendType:
        """Get trend description based on current and future values."""
        if current <= 0:
            return TrendType.STEADY
            
        percent_change = ((future - current) / current) * 100
        
        if abs(percent_change) < self.trend_threshold:
            return TrendType.STEADY
        elif percent_change > 0:
            return TrendType.BUILDING
        else:
            return TrendType.DROPPING

    def _get_coast_wind_quality(self, wind_dir: WindDirection, station: Station) -> str:
        """Determine wind direction relative to coast (offshore/onshore/etc)."""
        lon = station.location.coordinates[0]
        
        # East Coast (including Gulf Coast)
        east_coast = self.coast_config['east_coast']
        west_coast = self.coast_config['west_coast']
        
        if east_coast['min_lon'] <= lon <= east_coast['max_lon']:
            # East Coast wind quality
            return self._get_east_coast_wind_quality(wind_dir)
        # West Coast
        elif west_coast['min_lon'] <= lon <= west_coast['max_lon']:
            # West Coast wind quality
            return self._get_west_coast_wind_quality(wind_dir)
        # Default case (e.g. Hawaii, Alaska)
        else:
            return self._get_east_coast_wind_quality(wind_dir)
            
    def _get_east_coast_wind_quality(self, wind_dir: WindDirection) -> str:
        """Get wind quality for east coast."""
        # Perfect offshore: W
        # Semi offshore: NW, SW
        # Side-shore: N, S
        # Semi onshore: NE, SE
        # Direct onshore: E
        if wind_dir == WindDirection.W:
            return "offshore"
        elif wind_dir in {WindDirection.NW, WindDirection.SW}:
            return "semi-offshore"
        elif wind_dir in {WindDirection.N, WindDirection.S}:
            return "side-shore"
        elif wind_dir in {WindDirection.NE, WindDirection.SE}:
            return "semi-onshore"
        else:  # E
            return "onshore"
            
    def _get_west_coast_wind_quality(self, wind_dir: WindDirection) -> str:
        """Get wind quality for west coast."""
        # Perfect offshore: E
        # Semi offshore: NE, SE
        # Side-shore: N, S
        # Semi onshore: NW, SW
        # Direct onshore: W
        if wind_dir == WindDirection.E:
            return "offshore"
        elif wind_dir in {WindDirection.NE, WindDirection.SE}:
            return "semi-offshore"
        elif wind_dir in {WindDirection.N, WindDirection.S}:
            return "side-shore"
        elif wind_dir in {WindDirection.NW, WindDirection.SW}:
            return "semi-onshore"
        else:  # W
            return "onshore" 