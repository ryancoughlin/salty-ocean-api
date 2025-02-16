from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime

from .models import WaveCategory, WindCategory
from .trend_analyzer import TrendAnalyzer
from .conditions_scorer import ConditionsScorer

class WeatherSummaryService:
    def __init__(self):
        self.trend_analyzer = TrendAnalyzer()
        self.conditions_scorer = ConditionsScorer()

    def generate_summary(self, forecasts: List[Dict], station_metadata: Dict, 
                        current_observations: Optional[Dict] = None) -> Dict:
        """Generate a summary of current conditions and future trends."""
        if not forecasts:
            return {
                "conditions": None,
                "best_window": None
            }

        # Convert forecasts to DataFrame for easier analysis
        df = pd.DataFrame(forecasts)
        df['timestamp'] = pd.to_datetime(df['time'])
        
        # Get current data
        current_data = self._get_current_data(df, current_observations)
        
        # Analyze trends
        trends = self.trend_analyzer.analyze_trends(df)
        
        # Generate conditions summary
        conditions = self._generate_conditions_summary(current_data, trends, station_metadata)
        
        # Calculate scores and find best window
        scores = self._calculate_condition_scores(df, station_metadata)
        best_window = self.conditions_scorer.find_best_window(scores)

        return {
            "conditions": conditions,
            "best_window": best_window
        }

    def _get_current_data(self, df: pd.DataFrame, current_observations: Optional[Dict]) -> Dict:
        """Get current conditions from observations or nearest forecast."""
        if current_observations and 'wave' in current_observations and 'wind' in current_observations:
            return current_observations
        
        now = datetime.now(df['timestamp'].iloc[0].tzinfo)
        df['time_diff'] = abs(df['timestamp'] - now)
        current_idx = df['time_diff'].idxmin()
        return df.iloc[current_idx].to_dict()

    def _generate_conditions_summary(self, data: Dict, trends: Dict, metadata: Dict) -> Optional[str]:
        """Generate a human-readable summary of current conditions and trends."""
        if 'wave' not in data or 'wind' not in data:
            return None

        wave_height = data['wave'].get('height')
        wave_period = data['wave'].get('period')
        wind_speed = data['wind'].get('speed')
        wind_dir = data['wind'].get('direction')

        if not all([wave_height, wave_period, wind_speed, wind_dir]):
            return None

        # Get wave description
        wave_cat = WaveCategory.get_category(wave_height)
        wave_desc = f"{wave_cat} {wave_height:.1f}ft @ {wave_period:.0f}s"
            
        # Get wind description
        wind_cat = WindCategory.get_category(wind_speed)
        wind_cardinal = self.conditions_scorer._get_cardinal_direction(wind_dir)
        wind_desc = f"{wind_cat} {wind_cardinal}"
        
        # Combine descriptions
        summary = f"{wave_desc}, {wind_desc}"
        
        # Add trend if changing
        trend_desc = self.trend_analyzer.get_trend_description(trends)
        if trend_desc:
            summary += f". {trend_desc}"
                
        return summary

    def _calculate_condition_scores(self, df: pd.DataFrame, metadata: Dict) -> List[tuple]:
        """Calculate condition scores for each time point."""
        scores = []
        for _, row in df.iterrows():
            if 'wave' not in row or 'wind' not in row:
                continue

            wave_height = row['wave'].get('height')
            wave_period = row['wave'].get('period')
            wind_speed = row['wind'].get('speed')
            wind_dir = row['wind'].get('direction')
            
            if not all([wave_height, wave_period, wind_speed, wind_dir]):
                continue

            score = self.conditions_scorer.calculate_score(
                wave_height, wave_period, wind_speed, wind_dir, metadata
            )
            scores.append((row['timestamp'], score))

        return scores 