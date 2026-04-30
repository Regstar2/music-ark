"""Configuration layer for MusicArk core.

This module keeps config management provider-agnostic and platform-neutral.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .errors import ConfigError


@dataclass(slots=True)
class AppConfig:
    """Persisted app settings for v0.1 foundation."""

    database_path: str = ".musicark/musicark.db"
    log_level: str = "INFO"


def config_file_path(base_dir: Path | None = None) -> Path:
    """Return deterministic config location, defaulting to user home."""
    root = base_dir if base_dir is not None else Path.home()
    return root / ".musicark" / "config.json"


def load_config(base_dir: Path | None = None) -> AppConfig:
    """Load config from disk, creating default config if absent."""
    path = config_file_path(base_dir)
    if not path.exists():
        config = AppConfig()
        save_config(config, base_dir)
        return config

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig(
            database_path=str(payload.get("database_path", AppConfig.database_path)),
            log_level=str(payload.get("log_level", AppConfig.log_level)),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ConfigError(f"Failed to load config from '{path}'.") from exc


def save_config(config: AppConfig, base_dir: Path | None = None) -> Path:
    """Write config JSON atomically enough for local desktop usage."""
    path = config_file_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Failed to save config to '{path}'.") from exc
    return path
