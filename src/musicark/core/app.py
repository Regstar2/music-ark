"""Core application service for CLI commands in v0.1."""

from __future__ import annotations

from pathlib import Path

from .config import AppConfig, load_config
from musicark.storage.database import initialize_database
from musicark.providers import LocalLibraryProviderStub, ProviderRegistry
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.storage.provider_storage import ProviderStorageRepository


class MusicArkApp:
    """Composition root for core foundation services."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir
        self.config = load_config(base_dir)
        self.provider_registry = ProviderRegistry()
        self._register_default_providers()

    def _register_default_providers(self) -> None:
        """Register architecture stubs without coupling core to service API calls."""
        self.provider_registry.register(YandexMusicProvider(base_dir=self._base_dir))
        self.provider_registry.register(LocalLibraryProviderStub())

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
            "providers": self.provider_registry.list_ids(),
        }

    def db_init(self) -> Path:
        """Initialize storage schema and return DB path."""
        db_path = self.resolve_database_path()
        initialize_database(db_path)
        provider_storage = ProviderStorageRepository(db_path)
        for provider in self.provider_registry.list_providers():
            provider_storage.upsert_provider(provider)
        return db_path
