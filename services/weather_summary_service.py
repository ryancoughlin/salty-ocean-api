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

    def generate_summary(self, forecasts: List[Dict], station_metadata: Dict) -> Dict:
        if not forecasts:
            return {
                "current_conditions": None,
                "weekly_best": None,
                "overall_conditions": None
            }

        # Convert forecasts to DataFrame for easier analysis
        df = pd.DataFrame(forecasts)
        df['timestamp'] = pd.to_datetime(df['time'])
        
        # Get current conditions
        current = forecasts[0]
        current_summary = self._generate_current_summary(current, station_metadata)
        
        # Find best day in the next week
        weekly_best = self._find_best_day(df, station_metadata)
        
        # Generate overall conditions summary
        overall = self._generate_overall_summary(df, station_metadata)

        return {
            "current_conditions": current_summary,
            "weekly_best": weekly_best,
            "overall_conditions": overall
        }

    def _generate_current_summary(self, current: Dict, metadata: Dict) -> str:
        if 'wave' not in current or 'wind' not in current:
            return None

        wave_height = current['wave'].get('height')
        wave_period = current['wave'].get('period')
        wind_speed = current['wind'].get('speed')
        wind_dir = current['wind'].get('direction')

        if not all([wave_height, wave_period, wind_speed, wind_dir]):
            return None

        wave_cat = self._get_wave_category(wave_height)
        period_cat = self._get_period_category(wave_period)
        wind_cat = self._get_wind_category(wind_speed)
        wind_cardinal = self._get_cardinal_direction(wind_dir)

        return f"{wave_cat.capitalize()} {wave_height:.1f}ft waves at {wave_period:.0f}s intervals with {wind_cat} {wind_speed:.0f}mph {wind_cardinal} winds"

    def _find_best_day(self, df: pd.DataFrame, metadata: Dict) -> str:
        # Group by day
        df['date'] = df['timestamp'].dt.date
        daily_groups = df.groupby('date')

        best_score = float('-inf')
        best_day = None
        best_summary = None

        for date, day_data in daily_groups:
            # Skip if more than 7 days in future
            if date > datetime.now().date() + timedelta(days=7):
                continue

            # Calculate daily score based on conditions
            day_score = self._calculate_day_score(day_data, metadata)
            
            if day_score > best_score:
                best_score = day_score
                best_day = date
                
                # Get peak conditions for best day
                peak_conditions = self._get_peak_conditions(day_data)
                if peak_conditions:
                    best_summary = self._generate_current_summary(peak_conditions, metadata)

        if best_day and best_summary:
            return f"Best on {best_day.strftime('%A')}: {best_summary}"
        return None

    def _calculate_day_score(self, day_data: pd.DataFrame, metadata: Dict) -> float:
        score = 0
        for _, row in day_data.iterrows():
            if 'wave' not in row or 'wind' not in row:
                continue

            wave_height = row['wave'].get('height')
            wave_period = row['wave'].get('period')
            wind_speed = row['wind'].get('speed')
            wind_dir = row['wind'].get('direction')

            if not all([wave_height, wave_period, wind_speed, wind_dir]):
                continue

            # Base score on wave height (0-5)
            if 1 <= wave_height <= 5:  # 1ft to 5ft
                score += 5 - abs(3 - wave_height)  # Centered around 3ft
            
            # Bonus for good period (0-3)
            if wave_period >= 8:
                score += min((wave_period - 8) / 2, 3)
            
            # Penalty for strong winds (-5 to 0)
            if wind_speed > 15:  # > 15mph
                score -= min((wind_speed - 15) / 2, 5)
            
            # Bonus for favorable wind direction (0-2)
            if self._is_favorable_wind(wind_dir, metadata['location']['coordinates'][0]):
                score += 2

        return score / len(day_data)  # Average score for the day

    def _get_peak_conditions(self, day_data: pd.DataFrame) -> Optional[Dict]:
        if day_data.empty or 'wave' not in day_data.iloc[0]:
            return None
            
        # Find time with highest waves during favorable conditions
        best_conditions = None
        best_score = float('-inf')
        
        for _, row in day_data.iterrows():
            if 'wave' not in row or 'wind' not in row:
                continue
                
            wave_height = row['wave'].get('height')
            wind_speed = row['wind'].get('speed')
            
            if not all([wave_height, wind_speed]):
                continue
                
            # Simple scoring for peak conditions
            score = wave_height - (wind_speed / 5)  # Penalize strong winds
            
            if score > best_score:
                best_score = score
                best_conditions = row.to_dict()
                
        return best_conditions

    def _generate_overall_summary(self, df: pd.DataFrame, metadata: Dict) -> str:
        if df.empty:
            return None

        # Get average conditions
        avg_wave_height = df['wave'].apply(lambda x: x.get('height')).mean()
        avg_wind_speed = df['wind'].apply(lambda x: x.get('speed')).mean()
        
        # Count favorable wind periods
        favorable_winds = df['wind'].apply(lambda x: 
            self._is_favorable_wind(x.get('direction', 0), 
                                 metadata['location']['coordinates'][0]) 
            if x and 'direction' in x else False)
        favorable_pct = (favorable_winds.sum() / len(df)) * 100

        wave_cat = self._get_wave_category(avg_wave_height)
        wind_cat = self._get_wind_category(avg_wind_speed)

        conditions = []
        
        # Wave conditions
        conditions.append(f"{wave_cat} waves")
        
        # Wind conditions
        conditions.append(f"{wind_cat} winds")
        
        # Wind direction pattern
        if favorable_pct >= 60:
            conditions.append("mostly favorable winds")
        elif favorable_pct >= 40:
            conditions.append("mixed wind directions")
        else:
            conditions.append("mostly unfavorable winds")

        return f"{', '.join(conditions).capitalize()}" 