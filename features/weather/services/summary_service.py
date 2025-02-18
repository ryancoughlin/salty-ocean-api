import logging
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime

from features.weather.models.weather_types import WindCategory, TrendType
from features.weather.services.conditions_scorer import ConditionsScorer
from features.weather.services.trend_analyzer import TrendAnalyzer

logger = logging.getLogger(__name__)

class WeatherSummaryService:
    def __init__(self):
        pass

    def generate_summary(self, forecasts: List[Dict]) -> Optional[str]:
        """Generate a summary of conditions expected over the next 8 hours."""
        if not forecasts:
            return None

        try:
            # Convert forecasts to DataFrame for easier analysis
            df = pd.DataFrame(forecasts)
            df['timestamp'] = pd.to_datetime(df['time'])
            
            # Get next 8 hours of data using a proper rolling window
            now = datetime.now(df['timestamp'].iloc[0].tzinfo)
            window_end = now + pd.Timedelta(hours=8)
            next_8_hours = df[
                (df['timestamp'] >= now) & 
                (df['timestamp'] <= window_end)
            ].copy()
            
            if len(next_8_hours) < 2:
                return None

            # Analyze wave heights over the period (convert from meters to feet)
            wave_heights = next_8_hours['wave'].apply(lambda x: x['height'] * 3.28084)
            min_height = wave_heights.min()
            max_height = wave_heights.max()
            start_height = wave_heights.iloc[0]
            end_height = wave_heights.iloc[-1]
            height_diff = end_height - start_height
            
            # Determine wave trend description
            if max_height - min_height < 0.5:
                # If very little variation, just use the average
                avg_height = (max_height + min_height) / 2
                wave_trend = f"Holding steady at {avg_height:.1f} ft"
            elif abs(height_diff) < 0.5:
                # If start and end are similar but variation in between
                wave_trend = f"Varying between {min_height:.1f}-{max_height:.1f} ft"
            elif height_diff > 0:
                wave_trend = f"Building from {start_height:.1f} ft to {end_height:.1f} ft"
            else:
                wave_trend = f"Dropping from {start_height:.1f} ft to {end_height:.1f} ft"

            # Analyze wind trend
            start_wind = next_8_hours.iloc[0]['wind']
            end_wind = next_8_hours.iloc[-1]['wind']
            
            # Check if wind direction is changing significantly
            wind_dir_change = abs(end_wind['direction'] - start_wind['direction']) > 45
            
            # Get wind descriptions with speeds
            start_wind_cat = WindCategory.get_category(start_wind['speed'])
            end_wind_cat = WindCategory.get_category(end_wind['speed'])
            
            # Determine wind trend description
            if wind_dir_change:
                wind_desc = f"winds shifting from {start_wind_cat} {self._get_cardinal_direction(start_wind['direction'])} " \
                           f"({start_wind['speed']:.0f} mph) to {end_wind_cat} {self._get_cardinal_direction(end_wind['direction'])} " \
                           f"({end_wind['speed']:.0f} mph)"
            elif start_wind_cat != end_wind_cat:
                wind_desc = f"winds {start_wind_cat.lower()} ({start_wind['speed']:.0f} mph) becoming {end_wind_cat.lower()} ({end_wind['speed']:.0f} mph)"
            else:
                # If wind category stays the same, check for speed variation
                wind_speeds = next_8_hours['wind'].apply(lambda x: x['speed'])
                if max(wind_speeds) - min(wind_speeds) > 5:
                    wind_desc = f"with {start_wind_cat.lower()} {self._get_cardinal_direction(start_wind['direction'])} winds " \
                               f"varying {min(wind_speeds):.0f}-{max(wind_speeds):.0f} mph"
                else:
                    wind_desc = f"with {start_wind_cat.lower()} {self._get_cardinal_direction(start_wind['direction'])} winds " \
                               f"around {start_wind['speed']:.0f} mph"

            # Combine into final summary with better punctuation
            return f"{wave_trend}, {wind_desc}"

        except (KeyError, AttributeError, IndexError):
            return None

    def _get_cardinal_direction(self, degrees: float) -> str:
        """Convert degrees to cardinal direction."""
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index] 