"""MusicArk core package.

Keep package-level imports lightweight. ``MusicArkApp`` depends on providers,
while provider modules depend on ``musicark.core.errors``. Importing the app
eagerly here therefore creates an order-dependent circular import when a
provider is the first MusicArk module imported in a fresh Python process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import AppConfig, load_config, save_config
from .errors import ConfigError, MusicArkError, StorageError

if TYPE_CHECKING:
    from .app import MusicArkApp


def __getattr__(name: str) -> Any:
    """Lazily expose ``MusicArkApp`` without importing providers at package load."""
    if name == "MusicArkApp":
        from .app import MusicArkApp

        return MusicArkApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MusicArkApp",
    "AppConfig",
    "load_config",
    "save_config",
    "MusicArkError",
    "ConfigError",
    "StorageError",
]
