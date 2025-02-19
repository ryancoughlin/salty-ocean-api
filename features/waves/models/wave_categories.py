from enum import Enum

class WaveHeight(Enum):
    FLAT = (0, 0.5, "Flat")
    SMALL = (0.5, 2, "Small")
    MODERATE = (2, 4, "Moderate")
    LARGE = (4, 6, "Large")
    VERY_LARGE = (6, 8, "Very Large")
    HUGE = (8, 999, "Huge")

    def __init__(self, min_height: float, max_height: float, description: str):
        self.min_height = min_height
        self.max_height = max_height
        self.description = description

    @classmethod
    def from_height(cls, height: float) -> 'WaveHeight':
        for category in cls:
            if category.min_height <= height <= category.max_height:
                return category
        return cls.HUGE if height > 8 else cls.FLAT

class WavePeriod(Enum):
    SHORT = (0, 6, "Short")
    MEDIUM = (6, 10, "Medium")
    LONG = (10, 14, "Long")
    VERY_LONG = (14, 999, "Very Long")

    def __init__(self, min_period: float, max_period: float, description: str):
        self.min_period = min_period
        self.max_period = max_period
        self.description = description

    @classmethod
    def from_period(cls, period: float) -> 'WavePeriod':
        for category in cls:
            if category.min_period <= period <= category.max_period:
                return category
        return cls.VERY_LONG if period > 14 else cls.SHORT

class Conditions(Enum):
    CLEAN = "Clean"  # Light offshore winds, well-organized waves
    FAIR = "Fair"   # Light to moderate winds, slightly choppy
    ROUGH = "Rough" # Strong winds, choppy and disorganized

    @classmethod
    def from_wind_wave(cls, wind_speed: float, wind_direction: float, wave_direction: float) -> 'Conditions':
        # Calculate the difference between wind and wave direction
        dir_diff = abs((wind_direction - wave_direction + 180) % 360 - 180)
        
        if wind_speed < 10 and dir_diff > 135:  # Light offshore winds
            return cls.CLEAN
        elif wind_speed > 15 or dir_diff < 45:  # Strong winds or onshore
            return cls.ROUGH
        else:
            return cls.FAIR 