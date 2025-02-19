from enum import Enum

class BeaufortScale(Enum):
    CALM = (0, 1, "Calm")
    LIGHT_AIR = (1, 3, "Light Air")
    LIGHT_BREEZE = (4, 7, "Light Breeze")
    GENTLE_BREEZE = (8, 12, "Gentle Breeze")
    MODERATE_BREEZE = (13, 18, "Moderate Breeze")
    FRESH_BREEZE = (19, 24, "Fresh Breeze")
    STRONG_BREEZE = (25, 31, "Strong Breeze")
    NEAR_GALE = (32, 38, "Near Gale")
    GALE = (39, 46, "Gale")
    STRONG_GALE = (47, 54, "Strong Gale")
    STORM = (55, 63, "Storm")
    VIOLENT_STORM = (64, 72, "Violent Storm")
    HURRICANE = (73, 999, "Hurricane")

    def __init__(self, min_speed: int, max_speed: int, description: str):
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.description = description

    @classmethod
    def from_speed(cls, speed: float) -> 'BeaufortScale':
        for category in cls:
            if category.min_speed <= speed <= category.max_speed:
                return category
        return cls.HURRICANE if speed > 72 else cls.CALM

class WindDirection(Enum):
    N = (337.5, 22.5, "North")
    NE = (22.5, 67.5, "Northeast")
    E = (67.5, 112.5, "East")
    SE = (112.5, 157.5, "Southeast")
    S = (157.5, 202.5, "South")
    SW = (202.5, 247.5, "Southwest")
    W = (247.5, 292.5, "West")
    NW = (292.5, 337.5, "Northwest")

    def __init__(self, min_deg: float, max_deg: float, description: str):
        self.min_deg = min_deg
        self.max_deg = max_deg
        self.description = description

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
    STEADY = "steady"
    BUILDING = "building"
    DROPPING = "dropping" 