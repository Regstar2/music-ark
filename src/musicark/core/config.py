"""Configuration layer for MusicArk core.

This module keeps config management provider-agnostic and platform-neutral.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from .errors import ConfigError


@dataclass(slots=True)
class AppConfig:
    """Persisted app settings for v0.1 foundation."""

    database_path: str = ".musicark/musicark.db"
    log_level: str = "INFO"
    # Deprecated v0.10 research compatibility flag. Production manual upload in
    # v0.11.0 deliberately does not read this field as an enablement gate.
    experimental_yandex_upload: bool = False


def config_file_path(base_dir: Path | None = None) -> Path:
    """Return deterministic config location, defaulting to user home."""
    root = base_dir if base_dir is not None else Path.home()
    return root / ".musicark" / "config.json"


def load_config(base_dir: Path | None = None) -> AppConfig:
    """Load config from disk, creating default config if absent."""
    path = config_file_path(base_dir)
    if not path.exists():
        config = _apply_experimental_upload_env_override(AppConfig())
        save_config(config, base_dir)
        return config

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        exp_raw = payload.get("experimental_yandex_upload", False)
        if isinstance(exp_raw, str):
            experimental_yandex_upload = exp_raw.strip().lower() in ("1", "true", "yes", "on")
        else:
            experimental_yandex_upload = bool(exp_raw)
        cfg = AppConfig(
            database_path=str(payload.get("database_path", AppConfig.database_path)),
            log_level=str(payload.get("log_level", AppConfig.log_level)),
            experimental_yandex_upload=experimental_yandex_upload,
        )
        return _apply_experimental_upload_env_override(cfg)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ConfigError(f"Failed to load config from '{path}'.") from exc


def _apply_experimental_upload_env_override(config: AppConfig) -> AppConfig:
    """Preserve the deprecated research env override for backward compatibility."""
    raw = os.getenv("MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return AppConfig(
            database_path=config.database_path,
            log_level=config.log_level,
            experimental_yandex_upload=True,
        )
    return config


def save_config(config: AppConfig, base_dir: Path | None = None) -> Path:
    """Write config JSON atomically enough for local desktop usage."""
    path = config_file_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Failed to save config to '{path}'.") from exc
    return path
