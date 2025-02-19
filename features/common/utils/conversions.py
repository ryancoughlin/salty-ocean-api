from typing import Optional

class UnitConversions:
    """Centralized utility for unit conversions across the application."""
    
    @staticmethod
    def meters_to_feet(meters: Optional[float]) -> Optional[float]:
        """Convert meters to feet."""
        if meters is None:
            return None
        return round(meters * 3.28084, 2)
    
    @staticmethod
    def ms_to_mph(ms: Optional[float]) -> Optional[float]:
        """Convert meters per second to miles per hour."""
        if ms is None:
            return None
        return round(ms * 2.23694, 2)  # 1 m/s = 2.23694 mph 