from typing import Optional, Any, Callable
from aiocache import SimpleMemoryCache, caches
from aiocache.serializers import PickleSerializer

# Cache expiration times (in seconds)
MODEL_FORECAST_EXPIRE = 14400  # 4 hours - matches GFS model run frequency
CURRENT_CONDITIONS_EXPIRE = 900  # 15 minutes - real-time data
STATIC_DATA_EXPIRE = None  # No expiration for static data

# Configure default cache
caches.set_config({
    'default': {
        'cache': "aiocache.SimpleMemoryCache",
        'serializer': {
            'class': "aiocache.serializers.PickleSerializer"
        },
        'ttl': MODEL_FORECAST_EXPIRE,
    }
})

def get_cache() -> SimpleMemoryCache:
    """Get the default cache instance."""
    return caches.get('default')  # type: ignore

def feature_cache_key_builder(
    func: Callable,
    namespace: Optional[str] = None,
    *args: Any, 
    **kwargs: Any,
) -> str:
    """Standard cache key builder for station-specific endpoints.
    
    Args:
        func: The function being cached
        namespace: Optional namespace for the cache key
        args: Positional arguments passed to the function
        kwargs: Keyword arguments passed to the function
        
    Returns:
        str: Cache key in format {namespace}:{station_id}
    """
    # Get station_id from args if not in kwargs
    station_id = kwargs.get("station_id")
    if not station_id and args:
        station_id = args[0]  # First arg is station_id
    
    if not station_id:
        raise ValueError("station_id is required for caching")
        
    if not namespace:
        namespace = func.__name__
        
    # Ensure unique key per station
    return f"{namespace}:station:{station_id}" 