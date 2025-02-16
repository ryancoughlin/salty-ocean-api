from typing import Dict
import pandas as pd
from datetime import timedelta
from .models import TrendType

class TrendAnalyzer:
    @staticmethod
    def analyze_trends(df: pd.DataFrame) -> Dict[str, TrendType]:
        """Analyze wave and wind trends over the next 24 hours."""
        next_24h = df[df['timestamp'] <= df['timestamp'].iloc[0] + timedelta(hours=24)]
        
        if next_24h.empty:
            return {
                'wave': TrendType.STEADY,
                'wind': TrendType.STEADY
            }

        wave_heights = next_24h['wave'].apply(lambda x: x.get('height'))
        wind_speeds = next_24h['wind'].apply(lambda x: x.get('speed'))

        return {
            'wave': TrendAnalyzer._determine_trend(wave_heights),
            'wind': TrendAnalyzer._determine_trend(wind_speeds)
        }

    @staticmethod
    def _determine_trend(series: pd.Series) -> TrendType:
        """Determine if a series is steady, building, or dropping."""
        if series.empty:
            return TrendType.STEADY
            
        start_val = series.iloc[0]
        end_val = series.iloc[-1]
        change = end_val - start_val
        
        if abs(change) < 0.5:
            return TrendType.STEADY
        return TrendType.BUILDING if change > 0 else TrendType.DROPPING

    @staticmethod
    def get_trend_description(trends: Dict[str, TrendType]) -> str:
        """Get a human-readable description of the trends."""
        wave_trend = trends['wave']
        wind_trend = trends['wind']
        
        if wave_trend == TrendType.STEADY and wind_trend == TrendType.STEADY:
            return ""
            
        trend_map = {
            (TrendType.BUILDING, TrendType.STEADY): "Waves increasing",
            (TrendType.DROPPING, TrendType.STEADY): "Waves decreasing",
            (TrendType.STEADY, TrendType.BUILDING): "Winds increasing",
            (TrendType.STEADY, TrendType.DROPPING): "Winds decreasing",
            (TrendType.BUILDING, TrendType.BUILDING): "Conditions building",
            (TrendType.BUILDING, TrendType.DROPPING): "Waves up, winds down",
            (TrendType.DROPPING, TrendType.BUILDING): "Waves down, winds up",
            (TrendType.DROPPING, TrendType.DROPPING): "Conditions decreasing"
        }
        
        return trend_map.get((wave_trend, wind_trend), "") 