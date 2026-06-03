from enum import Enum
from typing import Optional

class ErrorCategory(str, Enum):
    CRITICAL = "critical"
    RECOVERABLE = "recoverable"
    WARNING = "warning"

class VideoEditorError(Exception):
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.CRITICAL, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.original_error = original_error

class AnalysisError(VideoEditorError):
    pass

class RenderingError(VideoEditorError):
    pass

class SubtitleError(VideoEditorError):
    pass

class StorageError(VideoEditorError):
    pass
