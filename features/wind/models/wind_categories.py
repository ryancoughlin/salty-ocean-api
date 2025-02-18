from enum import Enum

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