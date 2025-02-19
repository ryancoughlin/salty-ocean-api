from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from fastapi_cache.coder import Coder
from functools import wraps
from typing import Optional, Callable, Any
import logging
from fastapi.encoders import jsonable_encoder
import json
from datetime import datetime, timezone
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)

def datetime_handler(obj):
    """Handle datetime serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def convert_datetime_recursive(obj):
    """Recursively convert ISO datetime strings to datetime objects."""
    if isinstance(obj, dict):
        return {key: convert_datetime_recursive(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_recursive(item) for item in obj]
    elif isinstance(obj, str):
        try:
            return datetime.fromisoformat(obj)
        except ValueError:
            return obj
    return obj

class PydanticCoder(Coder):
    """Custom coder that uses FastAPI's built-in JSON handling."""
    @classmethod
    def encode(cls, value: Any) -> bytes:
        return json.dumps(jsonable_encoder(value)).encode()

    @classmethod
    def decode(cls, value: bytes) -> Any:
        return json.loads(value.decode())

async def init_cache():
    """Initialize in-memory cache backend."""
    FastAPICache.init(
        backend=InMemoryBackend(),
        prefix=settings.cache["prefix"]
    )
    logger.info("Initialized in-memory cache backend")

def cached(
    expire: Optional[int] = None,
    key_builder: Optional[Callable] = None,
    namespace: Optional[str] = None
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
            key_builder=key_builder,
            coder=PydanticCoder
        )(func)
        
    return decorator 