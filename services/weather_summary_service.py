from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta
from enum import Enum

class WaveCategory(Enum):
    FLAT = ((0, 1), "flat")
    VERY_SMALL = ((1, 2), "very small")
    SMALL = ((2, 3), "small")
    MODERATE = ((3, 5), "moderate")
    LARGE = ((5, 8), "large")
    VERY_LARGE = ((8, float('inf')), "very large")

    @classmethod
    def get_category(cls, height: float) -> str:
        for cat in cls:
            (min_height, max_height), _ = cat.value
            if min_height <= height < max_height:
                return cat.value[1]
        return "unknown"

class WindCategory(Enum):
    LIGHT = ((0, 5), "light")
    GENTLE = ((5, 10), "moderate")
    MODERATE = ((10, 15), "fresh")
    FRESH = ((15, 20), "strong")
    STRONG = ((20, 25), "very strong")
    GALE = ((25, float('inf')), "gale")

    @classmethod
    def get_category(cls, speed: float) -> str:
        for cat in cls:
            (min_speed, max_speed), _ = cat.value
            if min_speed <= speed < max_speed:
                return cat.value[1]
        return "unknown"

class TrendType(Enum):
    STEADY = "steady"
    BUILDING = "building"
    DROPPING = "dropping"

class WeatherSummaryService:
    def __init__(self):
        self.directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

    def _get_cardinal_direction(self, degrees: float) -> str:
        index = round(degrees / (360 / len(self.directions))) % len(self.directions)
        return self.directions[index]

    def _is_favorable_wind(self, wind_dir: float, longitude: float) -> bool:
        wind_cardinal = self._get_cardinal_direction(wind_dir)
        
        # East Coast (longitude < -100)
        if longitude > -100:
            favorable_winds = {"W", "NW", "SW"}
            return any(wind in wind_cardinal for wind in favorable_winds)
        # West Coast
        else:
            favorable_winds = {"E", "SE", "NE"}
            return any(wind in wind_cardinal for wind in favorable_winds)

    def generate_summary(self, forecasts: List[Dict], station_metadata: Dict, current_observations: Optional[Dict] = None) -> Dict:
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
        trends = self._analyze_trends(df)
        
        # Generate conditions summary
        conditions = self._generate_conditions_summary(current_data, trends, station_metadata)
        
        # Find best window
        best_window = self._find_best_window(df, station_metadata)

        return {
            "conditions": conditions,
            "best_window": best_window
        }

    def _get_current_data(self, df: pd.DataFrame, current_observations: Optional[Dict]) -> Dict:
        if current_observations and 'wave' in current_observations and 'wind' in current_observations:
            return current_observations
        
        now = datetime.now(df['timestamp'].iloc[0].tzinfo)
        df['time_diff'] = abs(df['timestamp'] - now)
        current_idx = df['time_diff'].idxmin()
        return df.iloc[current_idx].to_dict()

    def _analyze_trends(self, df: pd.DataFrame) -> Dict[str, TrendType]:
        next_24h = df[df['timestamp'] <= df['timestamp'].iloc[0] + timedelta(hours=24)]
        
        if next_24h.empty:
            return {
                'wave': TrendType.STEADY,
                'wind': TrendType.STEADY
            }

        wave_heights = next_24h['wave'].apply(lambda x: x.get('height'))
        wind_speeds = next_24h['wind'].apply(lambda x: x.get('speed'))

        return {
            'wave': self._determine_trend(wave_heights),
            'wind': self._determine_trend(wind_speeds)
        }

    def _determine_trend(self, series: pd.Series) -> TrendType:
        if series.empty:
            return TrendType.STEADY
            
        start_val = series.iloc[0]
        end_val = series.iloc[-1]
        change = end_val - start_val
        
        if abs(change) < 0.5:
            return TrendType.STEADY
        return TrendType.BUILDING if change > 0 else TrendType.DROPPING

    def _generate_conditions_summary(self, data: Dict, trends: Dict[str, TrendType], metadata: Dict) -> Optional[str]:
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
        wave_desc = f"{wave_cat} {wave_height:.1f}ft"
        
        # Add period
        wave_desc += f" @ {wave_period:.0f}s"
            
        # Get wind description
        wind_cat = WindCategory.get_category(wind_speed)
        wind_cardinal = self._get_cardinal_direction(wind_dir)
        wind_desc = f"{wind_cat} {wind_cardinal}"
        
        # Combine descriptions
        summary = f"{wave_desc}, {wind_desc}"
        
        # Add trend if changing
        trend_desc = self._get_trend_description(trends)
        if trend_desc:
            summary += f". {trend_desc}"
                
        return summary

    def _get_trend_description(self, trends: Dict[str, TrendType]) -> str:
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

    def _find_best_window(self, df: pd.DataFrame, metadata: Dict) -> Optional[str]:
        if df.empty:
            return None

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

            score = self._calculate_conditions_score(
                wave_height, wave_period, wind_speed, wind_dir, metadata
            )
            scores.append((row['timestamp'], score))

        return self._find_best_time_window(scores)

    def _calculate_conditions_score(self, wave_height: float, wave_period: float, 
                                 wind_speed: float, wind_dir: float, metadata: Dict) -> float:
        score = 0
        
        # Wave height scoring (optimal 2-4ft)
        if 2 <= wave_height <= 4:
            score += 5
        elif 1 <= wave_height <= 5:
            score += 3
        
        # Period scoring (longer is better)
        if wave_period >= 10:
            score += 3
        elif wave_period >= 7:
            score += 1

        # Wind scoring (less is better)
        if wind_speed < 10:
            score += 3
        elif wind_speed < 15:
            score += 1

        # Wind direction scoring
        if self._is_favorable_wind(wind_dir, metadata['location']['coordinates'][0]):
            score += 2

        return score

    def _find_best_time_window(self, scores: List[tuple]) -> Optional[str]:
        if not scores:
            return None

        best_start = None
        best_score = 0
        window_length = timedelta(hours=3)

        for i, (time, _) in enumerate(scores[:-2]):
            window_scores = [s[1] for s in scores[i:i+3]]
            avg_score = sum(window_scores) / 3
            
            if avg_score > best_score:
                best_score = avg_score
                best_start = time

        if best_start and best_score > 8:
            day = best_start.strftime("%A")
            time = best_start.strftime("%-I%p").lower()
            return f"Best conditions expected {day} at {time}"
            
        return None 