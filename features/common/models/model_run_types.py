from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Tuple

class ModelRunStatus(str, Enum):
    """Status of a model run cycle."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"

class ModelRunAttempt(BaseModel):
    """Record of an attempt to process a model run."""
    cycle_id: str = Field(..., description="Unique identifier for the cycle (YYYYMMDD_HH)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ModelRunStatus
    error: Optional[str] = None

class ModelRunConfig(BaseModel):
    """Configuration for model run processing."""
    check_interval_seconds: int = Field(default=300, description="Interval between cycle checks")
    retry_interval_seconds: int = Field(default=60, description="Interval between retries")
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")
    test_station_id: str = Field(default="44098", description="Station ID used for testing")
    test_location: Tuple[float, float] = Field(
        default=(40.0, -70.0),
        description="Test location (lat, lon) for wind data"
    )

class ModelCycle(str, Enum):
    """GFS model cycle hours."""
    CYCLE_00Z = "00"
    CYCLE_06Z = "06"
    CYCLE_12Z = "12"
    CYCLE_18Z = "18"
    
    @classmethod
    def get_cycle_hour(cls, cycle: str) -> int:
        """Get integer hour from cycle string."""
        return int(cycle)
    
    @classmethod
    def from_hour(cls, hour: int) -> "ModelCycle":
        """Get cycle from hour."""
        cycle = f"{hour:02d}"
        return cls(cycle)

class CycleStatus(str, Enum):
    """Status of a model cycle."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"

class CycleAttempt(BaseModel):
    """Track attempts to download a cycle."""
    cycle_id: str
    attempts: int = Field(default=0)
    last_attempt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: CycleStatus = Field(default=CycleStatus.PENDING)
    error: Optional[str] = Field(default=None)
    
    class Config:
        from_attributes = True

class ModelRunMetrics(BaseModel):
    """Metrics for model run service."""
    total_attempts: int = Field(default=0)
    successful_attempts: int = Field(default=0)
    failed_attempts: int = Field(default=0)
    last_successful_cycle: Optional[str] = Field(default=None)
    
    class Config:
        from_attributes = True 