from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from typing import Optional, Callable
import logging

from core.config import settings

logger = logging.getLogger(__name__)

async def init_cache():
    """Initialize in-memory cache backend."""
    FastAPICache.init(
        backend=InMemoryBackend(),
        prefix=settings.cache["prefix"]
    )

def cached(
    expire: Optional[int] = None,
    namespace: Optional[str] = None,
    key_builder: Optional[Callable] = None
):
    """Cache decorator that respects the enabled setting."""
    def decorator(func):
        if not settings.cache["enabled"]:
            return func
            
        # Get TTL from settings if not provided
        ttl = expire
        if ttl is None and namespace:
            ttl = settings.get_cache_ttl().get(namespace)
            
        return cache(
            expire=ttl,
            namespace=namespace or func.__name__,
            key_builder=key_builder
        )(func)
        
    return decorator 