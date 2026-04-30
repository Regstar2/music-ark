"""Provider registry for adapter lifecycle and lookup."""

from __future__ import annotations

from musicark.core.errors import MusicArkError

from .base import MusicProvider


class ProviderRegistryError(MusicArkError):
    """Raised when provider registration or lookup fails."""


class ProviderRegistry:
    """In-memory registry of music providers by provider_id."""

    def __init__(self) -> None:
        self._providers: dict[str, MusicProvider] = {}

    def register(self, provider: MusicProvider) -> None:
        """Register a provider adapter by its stable id."""
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ProviderRegistryError("Provider id must not be empty.")
        if provider_id in self._providers:
            raise ProviderRegistryError(f"Provider '{provider_id}' already registered.")
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> MusicProvider:
        """Return provider by id or raise if missing."""
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderRegistryError(f"Provider '{provider_id}' is not registered.") from exc

    def list_ids(self) -> list[str]:
        """Return sorted list of known provider ids."""
        return sorted(self._providers.keys())

    def list_providers(self) -> list[MusicProvider]:
        """Return providers sorted by provider id for deterministic order."""
        return [self._providers[key] for key in self.list_ids()]
