"""Core application errors used by MusicArk foundation modules."""


class MusicArkError(Exception):
    """Base exception for expected application-level failures."""


class ConfigError(MusicArkError):
    """Raised when configuration cannot be loaded or validated."""


class StorageError(MusicArkError):
    """Raised when SQLite storage operations fail."""


class MetadataEditorError(MusicArkError):
    """Raised when metadata read/write fails or violates validation rules."""
