class ModelRunError(Exception):
    """Base exception for model run errors."""
    pass

class CycleNotAvailableError(ModelRunError):
    """Raised when a cycle is not yet available."""
    pass

class CycleDownloadError(ModelRunError):
    """Raised when there's an error downloading cycle data."""
    pass

class CycleProcessingError(ModelRunError):
    """Raised when there's an error processing cycle data."""
    pass

class CycleValidationError(ModelRunError):
    """Raised when cycle data fails validation."""
    pass 