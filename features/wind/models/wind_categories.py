from enum import Enum
from .wind_types import BeaufortScaleEnum, WindDirectionEnum, TrendTypeEnum, BeaufortScaleModel, WindDirectionModel

class BeaufortScale(Enum):
    CALM = BeaufortScaleModel(category=BeaufortScaleEnum.CALM, min_speed=0, max_speed=1, description="Calm")
    LIGHT_AIR = BeaufortScaleModel(category=BeaufortScaleEnum.LIGHT_AIR, min_speed=1, max_speed=3, description="Light Air")
    LIGHT_BREEZE = BeaufortScaleModel(category=BeaufortScaleEnum.LIGHT_BREEZE, min_speed=4, max_speed=7, description="Light Breeze")
    GENTLE_BREEZE = BeaufortScaleModel(category=BeaufortScaleEnum.GENTLE_BREEZE, min_speed=8, max_speed=12, description="Gentle Breeze")
    MODERATE_BREEZE = BeaufortScaleModel(category=BeaufortScaleEnum.MODERATE_BREEZE, min_speed=13, max_speed=18, description="Moderate Breeze")
    FRESH_BREEZE = BeaufortScaleModel(category=BeaufortScaleEnum.FRESH_BREEZE, min_speed=19, max_speed=24, description="Fresh Breeze")
    STRONG_BREEZE = BeaufortScaleModel(category=BeaufortScaleEnum.STRONG_BREEZE, min_speed=25, max_speed=31, description="Strong Breeze")
    NEAR_GALE = BeaufortScaleModel(category=BeaufortScaleEnum.NEAR_GALE, min_speed=32, max_speed=38, description="Near Gale")
    GALE = BeaufortScaleModel(category=BeaufortScaleEnum.GALE, min_speed=39, max_speed=46, description="Gale")
    STRONG_GALE = BeaufortScaleModel(category=BeaufortScaleEnum.STRONG_GALE, min_speed=47, max_speed=54, description="Strong Gale")
    STORM = BeaufortScaleModel(category=BeaufortScaleEnum.STORM, min_speed=55, max_speed=63, description="Storm")
    VIOLENT_STORM = BeaufortScaleModel(category=BeaufortScaleEnum.VIOLENT_STORM, min_speed=64, max_speed=72, description="Violent Storm")
    HURRICANE = BeaufortScaleModel(category=BeaufortScaleEnum.HURRICANE, min_speed=73, max_speed=999, description="Hurricane")

    def __init__(self, model: BeaufortScaleModel):
        self.min_speed = model.min_speed
        self.max_speed = model.max_speed
        self.description = model.description
        self.category = model.category

    @classmethod
    def from_speed(cls, speed: float) -> 'BeaufortScale':
        for category in cls:
            if category.min_speed <= speed <= category.max_speed:
                return category
        return cls.HURRICANE if speed > 72 else cls.CALM

class WindDirection(Enum):
    N = WindDirectionModel(direction=WindDirectionEnum.N, min_deg=337.5, max_deg=22.5, description="North")
    NE = WindDirectionModel(direction=WindDirectionEnum.NE, min_deg=22.5, max_deg=67.5, description="Northeast")
    E = WindDirectionModel(direction=WindDirectionEnum.E, min_deg=67.5, max_deg=112.5, description="East")
    SE = WindDirectionModel(direction=WindDirectionEnum.SE, min_deg=112.5, max_deg=157.5, description="Southeast")
    S = WindDirectionModel(direction=WindDirectionEnum.S, min_deg=157.5, max_deg=202.5, description="South")
    SW = WindDirectionModel(direction=WindDirectionEnum.SW, min_deg=202.5, max_deg=247.5, description="Southwest")
    W = WindDirectionModel(direction=WindDirectionEnum.W, min_deg=247.5, max_deg=292.5, description="West")
    NW = WindDirectionModel(direction=WindDirectionEnum.NW, min_deg=292.5, max_deg=337.5, description="Northwest")

    def __init__(self, model: WindDirectionModel):
        self.min_deg = model.min_deg
        self.max_deg = model.max_deg
        self.description = model.description
        self.direction = model.direction

    @classmethod
    def from_degrees(cls, degrees: float) -> 'WindDirection':
        degrees = degrees % 360
        for direction in cls:
            if direction.min_deg <= degrees < direction.max_deg:
                return direction
        return cls.N  # Default for 337.5-360 and 0-22.5

class WindCategory(Enum):
    """Wind speed categories."""
    LIGHT = ((0, 5), "light")  # 0-5 m/s
    GENTLE = ((5, 10), "moderate")  # 5-10 m/s
    MODERATE = ((10, 15), "strong")  # 10-15 m/s
    STRONG = ((15, 20), "very strong")  # 15-20 m/s
    VERY_STRONG = ((20, 25), "high")  # 20-25 m/s
    GALE = ((25, float('inf')), "gale")  # >25 m/s

    @classmethod
    def get_category(cls, speed: float) -> str:
        """Get the wind category for a given speed in m/s."""
        for cat in cls:
            (min_speed, max_speed), _ = cat.value
            if min_speed <= speed < max_speed:
                return cat.value[1]
        return "unknown"

class TrendType(Enum):
    """Trend types for conditions."""
    STEADY = TrendTypeEnum.STEADY
    BUILDING = TrendTypeEnum.BUILDING
    DROPPING = TrendTypeEnum.DROPPING 