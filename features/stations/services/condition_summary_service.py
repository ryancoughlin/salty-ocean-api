import logging
from datetime import datetime, timedelta
from fastapi import HTTPException
from features.wind.models.wind_categories import WindDirection, TrendType
from features.waves.models.wave_categories import Conditions
from features.wind.services.wind_data_service import WindDataService
from features.waves.services.wave_data_service_v2 import WaveDataServiceV2
from features.stations.services.station_service import StationService
from features.common.models.station_types import Station
from features.stations.models.summary_types import ConditionSummaryResponse

logger = logging.getLogger(__name__)

class ConditionSummaryService:
    def __init__(
        self,
        wind_service: WindDataService,
        wave_service: WaveDataServiceV2,
        station_service: StationService
    ):
        self.wind_service = wind_service
        self.wave_service = wave_service
        self.station_service = station_service

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

            # Get current conditions
            current_wave = wave_forecast.forecasts[0]
            current_wind = wind_forecast.forecasts[0]

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
            wind_dir = WindDirection.from_degrees(current_wind.direction)
            conditions = Conditions.from_wind_wave(
                current_wind.speed,
                current_wind.direction,
                current_wave.direction if current_wave.direction is not None else 0.0
            )

            # Get trends
            wind_trend = self._get_trend_description(current_wind.speed, future_wind.speed)
            wave_trend = self._get_trend_description(
                current_wave.height if current_wave.height is not None else 0.0,
                future_wave.height if future_wave.height is not None else 0.0
            )
            wind_quality = self._get_coast_wind_quality(wind_dir, station)

            # Build summary
            wave_desc = f"{current_wave.height:.1f}ft"
            if current_wave.period:
                wave_desc += f" {current_wave.period:.0f}s"
            wave_desc += " waves"
            if wave_trend.value.lower() != "steady":
                wave_desc += f" are {wave_trend.value.lower()}"

            wind_desc = f"winds are {current_wind.speed:.0f}mph {wind_quality} from the {wind_dir.description.lower()}"
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
        
        if abs(percent_change) < 10:
            return TrendType.STEADY
        elif percent_change > 0:
            return TrendType.BUILDING
        else:
            return TrendType.DROPPING

    def _get_coast_wind_quality(self, wind_dir: WindDirection, station: Station) -> str:
        """Determine wind direction relative to coast (offshore/onshore/etc)."""
        # East Coast (including Gulf Coast)
        if station.location.coordinates[0] > -100 and station.location.coordinates[0] < -60:
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
        # West Coast
        elif station.location.coordinates[0] <= -100:
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
        # Default case (e.g. Hawaii, Alaska)
        else:
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