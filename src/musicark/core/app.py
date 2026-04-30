"""Core application service for CLI commands in v0.1."""

from __future__ import annotations

from pathlib import Path

from .config import AppConfig, load_config
from musicark.storage.database import initialize_database


class MusicArkApp:
    """Composition root for core foundation services."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir
        self.config = load_config(base_dir)

    def resolve_database_path(self) -> Path:
        """Resolve configured DB path relative to base directory/home."""
        raw_path = Path(self.config.database_path)
        if raw_path.is_absolute():
            return raw_path
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw_path

    def health_check(self) -> dict[str, str | bool]:
        """Return simple health state for the CLI."""
        db_path = self.resolve_database_path()
        return {
            "status": "ok",
            "database_exists": db_path.exists(),
            "database_path": str(db_path),
        }

    def db_init(self) -> Path:
        """Initialize storage schema and return DB path."""
        db_path = self.resolve_database_path()
        initialize_database(db_path)
        return db_path
