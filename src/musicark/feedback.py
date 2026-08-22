"""Privacy-preserving GitHub feedback entry points for the desktop app."""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
from urllib.parse import urlencode, urlsplit, urlunsplit

from musicark import __version__

_DEFAULT_REPOSITORY = "https://github.com/Regstar2/music-ark"


@dataclass(frozen=True, slots=True)
class FeedbackLink:
    kind: str
    url: str

    def public_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "url": self.url}


def _repository_url() -> str:
    value = str(os.getenv("MUSICARK_PUBLIC_REPOSITORY_URL") or _DEFAULT_REPOSITORY).strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme.casefold() != "https" or (parsed.hostname or "").casefold() != "github.com":
        return _DEFAULT_REPOSITORY
    parts = [item for item in parsed.path.split("/") if item]
    if len(parts) != 2:
        return _DEFAULT_REPOSITORY
    return urlunsplit(("https", "github.com", f"/{parts[0]}/{parts[1]}", "", ""))


def _environment_block() -> str:
    # Deliberately excludes paths, account identity, tokens, library contents,
    # provider payloads and network credentials.
    return "\n".join(
        [
            "",
            "---",
            "MusicArk diagnostics (safe subset)",
            f"Version: {__version__}",
            f"OS: {platform.system()} {platform.release()}",
            f"Architecture: {platform.machine()}",
        ]
    )


def feedback_link(kind: str) -> FeedbackLink:
    normalized = str(kind).strip().casefold()
    if normalized not in {"bug", "feature"}:
        raise ValueError("Feedback kind must be 'bug' or 'feature'.")
    template = "bug_report.yml" if normalized == "bug" else "feature_request.yml"
    base = f"{_repository_url()}/issues/new"
    query = {"template": template}
    if normalized == "bug":
        query["body"] = _environment_block()
    return FeedbackLink(normalized, f"{base}?{urlencode(query)}")


def open_feedback(kind: str) -> dict[str, str | bool]:
    link = feedback_link(kind)
    if os.name != "nt":
        return {"opened": False, **link.public_dict()}
    try:
        os.startfile(link.url)  # type: ignore[attr-defined]  # Windows ShellExecute URL handler.
    except OSError:
        return {"opened": False, **link.public_dict()}
    return {"opened": True, **link.public_dict()}
