from typing import Dict, List, Tuple
from datetime import datetime, timedelta

class ConditionsScorer:
    @staticmethod
    def find_best_window(scores: List[Tuple[datetime, float]]) -> str:
        """Find the best 3-hour window based on condition scores."""
        if not scores:
            return None

        best_start = None
        best_score = 0

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

    @staticmethod
    def calculate_score(wave_height: float, wave_period: float, 
                       wind_speed: float, wind_dir: float, 
                       metadata: Dict) -> float:
        """Calculate a score for the given conditions."""
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
        if ConditionsScorer._is_favorable_wind(wind_dir, metadata['location']['coordinates'][0]):
            score += 2

        return score

    @staticmethod
    def _is_favorable_wind(wind_dir: float, longitude: float) -> bool:
        """Check if wind direction is favorable for the given location."""
        wind_cardinal = ConditionsScorer._get_cardinal_direction(wind_dir)
        
        # East Coast (longitude < -100)
        if longitude > -100:
            favorable_winds = {"W", "NW", "SW"}
            return any(wind in wind_cardinal for wind in favorable_winds)
        # West Coast
        else:
            favorable_winds = {"E", "SE", "NE"}
            return any(wind in wind_cardinal for wind in favorable_winds)

    @staticmethod
    def _get_cardinal_direction(degrees: float) -> str:
        """Convert degrees to cardinal direction."""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / (360 / len(directions))) % len(directions)
        return directions[index] 