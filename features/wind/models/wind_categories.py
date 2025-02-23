from enum import Enum
from .wind_types import WindDirectionEnum, TrendTypeEnum, WindDirectionModel


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