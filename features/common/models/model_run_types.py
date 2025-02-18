from datetime import datetime, time, timedelta, timezone
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

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

class ModelRunConfig(BaseModel):
    """Configuration for model run service."""
    cycles: list[ModelCycle] = Field(
        default=[ModelCycle.CYCLE_00Z, ModelCycle.CYCLE_06Z, 
                ModelCycle.CYCLE_12Z, ModelCycle.CYCLE_18Z]
    )
    processing_delay_hours: int = Field(default=6)
    max_attempts: int = Field(default=5)
    min_retry_delay_minutes: int = Field(default=15)
    
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