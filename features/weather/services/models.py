from enum import Enum

class WindCategory(Enum):
    LIGHT = ((0, 5), "light")
    GENTLE = ((5, 10), "moderate")
    MODERATE = ((10, 15), "strong")
    STRONG = ((15, 20), "very strong")
    VERY_STRONG = ((20, 25), "high")
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