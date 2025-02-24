import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    """Shared rate limiter for API clients to avoid request throttling."""
    
    def __init__(
        self,
        requests_per_minute: int = 120,
        batch_size: int = 30,
        batch_pause: int = 15
    ):
        """Initialize rate limiter with configurable parameters.
        
        Args:
            requests_per_minute: Maximum requests per minute
            batch_size: Number of requests before pausing
            batch_pause: Seconds to pause after a batch
        """
        self.requests_per_minute = requests_per_minute
        self.request_interval = 60 / requests_per_minute  # Time between requests in seconds
        self.batch_size = batch_size
        self.batch_pause = batch_pause
        self._request_count = 0
        self._last_request_time = datetime.now()
        
    async def limit(self):
        """Apply rate limiting logic before making a request."""
        now = datetime.now()
        
        # Reset counter if a minute has passed
        if (now - self._last_request_time).total_seconds() >= 60:
            self._request_count = 0
            self._last_request_time = now
            
        # If we've hit our batch size, pause
        if self._request_count > 0 and self._request_count % self.batch_size == 0:
            logger.info(f"⏸️ Pausing for {self.batch_pause}s after batch of {self.batch_size} requests...")
            await asyncio.sleep(self.batch_pause)
            self._request_count = 0
            self._last_request_time = datetime.now()
            return
            
        # Otherwise, small delay between requests
        if self._request_count > 0:
            await asyncio.sleep(self.request_interval)
            
        self._request_count += 1 