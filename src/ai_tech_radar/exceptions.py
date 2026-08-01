"""Application-specific exceptions."""


class TechRadarError(Exception):
    """Base exception for the AI Tech Radar application."""


class ConfigError(TechRadarError):
    """Raised when configuration files are missing or invalid."""


class CollectionError(TechRadarError):
    """Raised when a collector cannot process a source."""


class StorageError(TechRadarError):
    """Raised when the SQLite storage layer fails."""


class AnalysisError(TechRadarError):
    """Raised when article analysis fails."""


class ReportError(TechRadarError):
    """Raised when a report cannot be generated."""
