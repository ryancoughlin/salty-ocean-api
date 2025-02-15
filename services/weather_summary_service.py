from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta

class WeatherSummaryService:
    def __init__(self):
        self.wave_height_categories = {
            (0, 1): "flat",
            (1, 2): "very small",
            (2, 3): "small",
            (3, 5): "moderate",
            (5, 8): "large",
            (8, float('inf')): "very large"
        }
        
        self.wind_speed_categories = {
            (0, 5): "light",
            (5, 10): "gentle",
            (10, 15): "moderate",
            (15, 20): "fresh",
            (20, 25): "strong",
            (25, float('inf')): "gale"
        }
        
        self.wave_period_categories = {
            (0, 6): "short",
            (6, 10): "medium",
            (10, float('inf')): "long"
        }

    def _get_wind_category(self, speed: float) -> str:
        for (min_speed, max_speed), category in self.wind_speed_categories.items():
            if min_speed <= speed < max_speed:
                return category
        return "unknown"

    def _get_wave_category(self, height: float) -> str:
        for (min_height, max_height), category in self.wave_height_categories.items():
            if min_height <= height < max_height:
                return category
        return "unknown"

    def _get_period_category(self, period: float) -> str:
        for (min_period, max_period), category in self.wave_period_categories.items():
            if min_period <= period < max_period:
                return category
        return "unknown"

    def _get_cardinal_direction(self, degrees: float) -> str:
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / (360 / len(directions))) % len(directions)
        return directions[index]

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
        current_data = None
        if current_observations and 'wave' in current_observations and 'wind' in current_observations:
            current_data = current_observations
        else:
            now = datetime.now(df['timestamp'].iloc[0].tzinfo)
            df['time_diff'] = abs(df['timestamp'] - now)
            current_idx = df['time_diff'].idxmin()
            current_data = forecasts[current_idx]

        # Analyze next 24 hours for trend
        next_24h = df[df['timestamp'] <= df['timestamp'].iloc[0] + timedelta(hours=24)]
        wave_trend = None
        wind_trend = None
        if not next_24h.empty:
            wave_trend = self._analyze_trend(next_24h['wave'].apply(lambda x: x.get('height')))
            wind_trend = self._analyze_trend(next_24h['wind'].apply(lambda x: x.get('speed')))

        # Generate combined conditions summary
        conditions = self._generate_conditions_summary(current_data, wave_trend, wind_trend, station_metadata)

        # Find best window in next 3 days
        best_window = self._find_best_window(df[:72], station_metadata)  # Look at next 72 hours

        return {
            "conditions": conditions,
            "best_window": best_window
        }

    def _analyze_trend(self, series: pd.Series) -> str:
        """Analyze if a series is holding, building, or dropping."""
        if series.empty:
            return "steady"
            
        start_val = series.iloc[0]
        end_val = series.iloc[-1]
        change = end_val - start_val
        
        if abs(change) < 0.5:  # Less than 0.5 change is considered steady
            return "steady"
        return "building" if change > 0 else "dropping"

    def _generate_conditions_summary(self, data: Dict, wave_trend: Optional[str], wind_trend: Optional[str], metadata: Dict) -> Optional[str]:
        """Generate a concise summary combining current conditions with trends."""
        if 'wave' not in data or 'wind' not in data:
            return None

        wave_height = data['wave'].get('height')
        wave_period = data['wave'].get('period')
        wind_speed = data['wind'].get('speed')
        wind_dir = data['wind'].get('direction')

        if not all([wave_height, wave_period, wind_speed, wind_dir]):
            return None

        wave_cat = self._get_wave_category(wave_height)
        wind_cat = self._get_wind_category(wind_speed)
        wind_cardinal = self._get_cardinal_direction(wind_dir)
        
        # Base conditions
        summary = f"{wave_cat.capitalize()} {wave_height:.1f}ft @ {wave_period:.0f}s, {wind_cat} {wind_cardinal}"
        
        # Add trend if available
        if wave_trend and wind_trend:
            trend_text = self._get_trend_suffix(wave_trend, wind_trend)
            if trend_text:
                summary += f" ({trend_text})"
                
        return summary

    def _get_trend_suffix(self, wave_trend: str, wind_trend: str) -> str:
        """Get a concise trend suffix."""
        if wave_trend == "steady" and wind_trend == "steady":
            return ""  # Don't add trend if everything is steady
            
        trends = {
            ("building", "steady"): "building",
            ("dropping", "steady"): "dropping",
            ("steady", "building"): "winds increasing",
            ("steady", "dropping"): "winds easing",
            ("building", "building"): "all building",
            ("building", "dropping"): "building + winds easing",
            ("dropping", "building"): "dropping + winds building",
            ("dropping", "dropping"): "all easing"
        }
        return trends.get((wave_trend, wind_trend), "")

    def _find_best_window(self, df: pd.DataFrame, metadata: Dict) -> Optional[str]:
        """Find the best time window in the forecast period."""
        if df.empty:
            return None

        # Calculate score for each hour
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

            # Score based on ideal conditions
            score = 0
            # Wave height (optimal 2-4ft)
            if 2 <= wave_height <= 4:
                score += 5
            elif 1 <= wave_height <= 5:
                score += 3
            
            # Period (longer is better)
            if wave_period >= 10:
                score += 3
            elif wave_period >= 7:
                score += 1

            # Wind (less is better)
            if wind_speed < 10:
                score += 3
            elif wind_speed < 15:
                score += 1

            # Favorable wind direction
            if self._is_favorable_wind(wind_dir, metadata['location']['coordinates'][0]):
                score += 2

            scores.append((row['timestamp'], score))

        if not scores:
            return None

        # Find best continuous window (at least 3 hours with good scores)
        best_start = None
        best_score = 0
        window_length = timedelta(hours=3)

        for i, (time, _) in enumerate(scores[:-2]):  # Look for 3-hour windows
            window_scores = [s[1] for s in scores[i:i+3]]  # Get 3 consecutive scores
            avg_score = sum(window_scores) / 3
            
            if avg_score > best_score:
                best_score = avg_score
                best_start = time

        if best_start and best_score > 8:  # Only return if it's actually good conditions
            day = best_start.strftime("%A")
            time = best_start.strftime("%-I%p").lower()
            return f"Best conditions {day} {time}"
            
        return None 