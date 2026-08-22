"""Typed, fail-closed contracts for MusicArk desktop updates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

_VERSION_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UpdateChannel(StrEnum):
    STABLE = "stable"
    BETA = "beta"


class UpdateErrorCode(StrEnum):
    CHANNEL_NOT_CONFIGURED = "channel_not_configured"
    NETWORK_FAILED = "network_failed"
    MANIFEST_INVALID = "manifest_invalid"
    UNTRUSTED_URL = "untrusted_url"
    DOWNLOAD_FAILED = "download_failed"
    HASH_MISMATCH = "hash_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    INSTALLER_LAUNCH_FAILED = "installer_launch_failed"


class UpdateError(RuntimeError):
    def __init__(self, code: UpdateErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, order=True, slots=True)
class AppVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "AppVersion":
        match = _VERSION_RE.fullmatch(str(value).strip())
        if match is None:
            raise ValueError("Version must use strict MAJOR.MINOR.PATCH SemVer syntax.")
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch")))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, slots=True)
class InstallerAsset:
    url: str
    sha256: str
    size_bytes: int
    file_name: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InstallerAsset":
        url = str(payload.get("url", "")).strip()
        sha256 = str(payload.get("sha256", "")).strip().lower()
        file_name = str(payload.get("fileName", "")).strip()
        try:
            size_bytes = int(payload.get("sizeBytes", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("Installer sizeBytes must be an integer.") from exc
        if not url:
            raise ValueError("Installer URL is required.")
        if _SHA256_RE.fullmatch(sha256) is None:
            raise ValueError("Installer sha256 must contain exactly 64 lowercase hex characters.")
        if size_bytes <= 0 or size_bytes > 1_073_741_824:
            raise ValueError("Installer sizeBytes must be between 1 byte and 1 GiB.")
        if not file_name or file_name != file_name.replace("\\", "/").split("/")[-1]:
            raise ValueError("Installer fileName must be a plain file name.")
        if not file_name.casefold().endswith(".exe"):
            raise ValueError("Windows update asset must be an .exe installer.")
        return cls(url=url, sha256=sha256, size_bytes=size_bytes, file_name=file_name)

    def public_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "sha256": self.sha256,
            "sizeBytes": self.size_bytes,
            "fileName": self.file_name,
        }


@dataclass(frozen=True, slots=True)
class UpdateManifest:
    schema_version: int
    channel: UpdateChannel
    version: AppVersion
    published_at: str
    installer: InstallerAsset
    release_notes_url: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UpdateManifest":
        try:
            schema = int(payload.get("schemaVersion", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("schemaVersion must be an integer.") from exc
        if schema != 1:
            raise ValueError("Unsupported update manifest schemaVersion.")
        try:
            channel = UpdateChannel(str(payload.get("channel", "")).strip())
        except ValueError as exc:
            raise ValueError("Unsupported update channel.") from exc
        version = AppVersion.parse(str(payload.get("version", "")))
        published_at = str(payload.get("publishedAt", "")).strip()
        if not published_at:
            raise ValueError("publishedAt is required.")
        raw_installer = payload.get("installer")
        if not isinstance(raw_installer, dict):
            raise ValueError("installer object is required.")
        release_notes = str(payload.get("releaseNotesUrl", "")).strip() or None
        return cls(
            schema_version=schema,
            channel=channel,
            version=version,
            published_at=published_at,
            installer=InstallerAsset.from_dict(raw_installer),
            release_notes_url=release_notes,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "channel": self.channel.value,
            "version": str(self.version),
            "publishedAt": self.published_at,
            "installer": self.installer.public_dict(),
            "releaseNotesUrl": self.release_notes_url,
        }
