from datetime import datetime, timedelta
from typing import Tuple
from fastapi import HTTPException
import asyncio
import logging

from features.wind.models.wind_types import WindForecastResponse
from features.waves.models.wave_types import WaveForecastPoint, WaveForecastResponse
from features.wind.models.wind_categories import BeaufortScale, WindDirection, TrendType
from features.waves.models.wave_categories import WaveHeight, WavePeriod, Conditions
from features.wind.services.wind_service import WindService
from features.waves.services.wave_data_service import WaveDataService
from features.stations.services.station_service import StationService
from features.common.models.station_types import Station
from features.stations.models.summary_types import ConditionSummaryResponse
from core.cache import cached

logger = logging.getLogger(__name__)

def build_summary_cache_key(func, namespace: str = "", **kwargs) -> str:
    """Build cache key for station summaries."""
    station_id = kwargs.get("station_id", "")
    return f"{namespace}:{station_id}"

class ConditionSummaryService:
    def __init__(
        self,
        wind_service: WindService,
        wave_service: WaveDataService,
        station_service: StationService
    ):
        self.wind_service = wind_service
        self.wave_service = wave_service
        self.station_service = station_service

    def _get_trend_description(self, current: float, future: float) -> TrendType:
        """Get trend description based on current and future values."""
        if current <= 0:
            return TrendType.STEADY
            
        percent_change = ((future - current) / current) * 100
        
        if abs(percent_change) < 10:
            return TrendType.STEADY
        elif percent_change > 0:
            return TrendType.BUILDING
        else:
            return TrendType.DROPPING

    def _get_coast_wind_quality(self, wind_dir: WindDirection, station: Station) -> str:
        """Determine if wind direction is favorable based on coast location."""
        # East Coast
        if station.location.coordinates[0] < -50:  # Rough estimate of east coast longitude
            favorable = {WindDirection.W, WindDirection.NW, WindDirection.SW}
            return "favorable" if wind_dir in favorable else "unfavorable"
        # West Coast
        else:
            favorable = {WindDirection.E, WindDirection.SE, WindDirection.NE}
            return "favorable" if wind_dir in favorable else "unfavorable"

    async def _get_forecast_data(self, station_id: str) -> Tuple[WindForecastResponse, WaveForecastResponse]:
        """Fetch all forecast data in parallel."""
        wind_forecast, wave_forecast = await asyncio.gather(
            self.wind_service.get_station_wind_forecast(station_id),
            self.wave_service.get_station_forecast(station_id),
            return_exceptions=True
        )

        # Check each result individually for better error reporting
        if isinstance(wind_forecast, Exception):
            logger.error(f"Wind forecast error for {station_id}: {str(wind_forecast)}")
            raise HTTPException(
                status_code=503, 
                detail=f"Unable to fetch wind conditions: {str(wind_forecast)}"
            )
            
        if isinstance(wave_forecast, Exception):
            if isinstance(wave_forecast, HTTPException) and wave_forecast.status_code == 404:
                # This is an expected case - station doesn't have wave forecasts
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} does not have wave forecasts available"
                )
            logger.error(f"Wave forecast error for {station_id}: {str(wave_forecast)}")
            raise HTTPException(
                status_code=503, 
                detail=f"Unable to fetch wave conditions: {str(wave_forecast)}"
            )

        if not wind_forecast:
            raise HTTPException(status_code=503, detail="No wind forecast data available")
            
        if not wave_forecast:
            raise HTTPException(status_code=404, detail=f"Station {station_id} does not have wave forecasts available")

        if not wind_forecast.forecasts:
            raise HTTPException(status_code=503, detail="Wind forecast contains no data points")
            
        if not wave_forecast.forecasts:
            raise HTTPException(status_code=503, detail="Wave forecast contains no data points")

        return wind_forecast, wave_forecast

    @cached(
        namespace="station_summary",
        expire=900,  # 15 minutes in seconds
        key_builder=build_summary_cache_key
    )
    async def get_station_condition_summary(self, station_id: str) -> ConditionSummaryResponse:
        """Generate a human-readable summary of current conditions and trends."""
        try:
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

            wind_forecast, wave_forecast = await self._get_forecast_data(station_id)

            # Get current wave data
            current_wave = wave_forecast.forecasts[0]
            if not current_wave:
                raise HTTPException(status_code=503, detail="No wave data available")

            # Get current wind data (first forecast point)
            current_wind = wind_forecast.forecasts[0]
            if not current_wind:
                raise HTTPException(status_code=503, detail="No wind data available")

            # Get conditions in 6 hours
            future_time = datetime.now(current_wave.time.tzinfo) + timedelta(hours=6)
            future_wind = next(
                (f for f in wind_forecast.forecasts if f.time >= future_time),
                wind_forecast.forecasts[-1]
            )
            future_wave = next(
                (f for f in wave_forecast.forecasts if f.time >= future_time),
                wave_forecast.forecasts[-1]
            )

            # Calculate categories
            wind_category = BeaufortScale.from_speed(current_wind.speed)
            wind_dir = WindDirection.from_degrees(current_wind.direction)
            wave_height = WaveHeight.from_height(current_wave.height)
            wave_period = WavePeriod.from_period(current_wave.period or 0)
            conditions = Conditions.from_wind_wave(
                current_wind.speed,
                current_wind.direction,
                current_wave.direction
            )

            # Get trends
            wind_trend = self._get_trend_description(current_wind.speed, future_wind.speed)
            wave_trend = self._get_trend_description(current_wave.height, future_wave.height)
            wind_quality = self._get_coast_wind_quality(wind_dir, station)

            # Build summary
            summary_parts = [
                f"{wave_height.description} {current_wave.height:.1f}ft waves"
            ]
            
            if current_wave.period:
                summary_parts.append(f"at {current_wave.period:.0f}s intervals")
                
            summary_parts.extend([
                f"{wave_trend.value}",
                f"with {wind_category.description.lower()}",
                f"{current_wind.speed:.0f}mph {wind_dir.description.lower()} winds ({wind_quality})",
                f"{wind_trend.value}",
                f"Conditions are {conditions.value.lower()}"
            ])

            summary = ", ".join(summary_parts[:-1]) + ". " + summary_parts[-1] + "."

            return ConditionSummaryResponse(
                station=station,
                summary=summary,
                generated_at=datetime.now(current_wave.time.tzinfo)
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error generating condition summary: {str(e)}"
            ) 