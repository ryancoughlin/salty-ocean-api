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