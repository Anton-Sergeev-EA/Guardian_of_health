"""
Custom exceptions for FocusGuardian.
All exceptions inherit from the base FocusGuardianError to allow
unified error handling across the application.
"""


class FocusGuardianError(Exception):
    """Base exception for all FocusGuardian runtime errors."""
    pass


class CameraError(FocusGuardianError):
    """Raised when camera initialization, configuration, or frame capture fails."""
    pass


class ModelError(FocusGuardianError):
    """Raised when machine learning models (MediaPipe, C++ engine) fail to load or process."""
    pass


class ConfigError(FocusGuardianError):
    """Raised when configuration parsing, validation, or loading fails."""
    pass


class DatabaseError(FocusGuardianError):
    """Raised when SQLite database operations, connection, or migrations fail."""
    pass


class VoiceError(FocusGuardianError):
    """Raised when Vosk model initialization or microphone stream access fails."""
    pass


class WebError(FocusGuardianError):
    """Raised when Flask/Socket.IO server initialization or network binding fails."""
    pass


class ValidationError(FocusGuardianError):
    """Raised when input parameters, configurations, or metric values fail validation."""
    pass
