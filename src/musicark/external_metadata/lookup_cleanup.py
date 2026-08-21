"""Conservative cleanup for catalog lookup queries.

This module removes obvious distribution/site advertising noise from local tags
before they are sent to catalog search. It deliberately preserves semantic
version markers such as [Live], [Remix], [Acoustic], etc.
"""

from __future__ import annotations

import re
import unicodedata


_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_BRACKETED = re.compile(r"\[([^\[\]]{1,120})\]|\(([^()]{1,120})\)")
_DOMAIN = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:ru|com|net|org|me|io|cc|su|xyz|site|online|pro|club)\b",
    re.IGNORECASE,
)
_JUNK = re.compile(
    r"(?:"
    r"drive[\s._-]*music|drivemusic|"
    r"vk\.com|t\.me|telegram|"
    r"скачать|download|free\s+download|"
    r"(?:^|\b)mp3(?:\b|$)|(?:128|192|256|320)\s*kbps|"
    r"music\s*(?:site|portal|download)"
    r")",
    re.IGNORECASE,
)
_SEPARATOR = re.compile(r"\s{2,}")
_LEADING_JUNK = re.compile(
    r"^(?:drive[\s._-]*music|drivemusic(?:\.[a-z]{2,})?|(?:[a-z0-9-]+\.)+(?:ru|com|net|org|me))\s*[-–—:|]+\s*",
    re.IGNORECASE,
)


def _looks_like_junk(value: str) -> bool:
    text = value.strip()
    return bool(_JUNK.search(text) or _DOMAIN.search(text) or _URL.search(text))


def sanitize_lookup_text(value: str | None) -> str:
    """Remove obvious site/distribution noise without deleting music semantics."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = _URL.sub(" ", text)

    def bracket_replacement(match: re.Match[str]) -> str:
        inner = (match.group(1) or match.group(2) or "").strip()
        return " " if _looks_like_junk(inner) else match.group(0)

    text = _BRACKETED.sub(bracket_replacement, text)
    text = _LEADING_JUNK.sub("", text.strip())

    # Bare domains/site names at the ends are common in downloaded tags. Remove
    # only the obviously promotional token itself; do not strip arbitrary words.
    tokens = text.split()
    while tokens and _looks_like_junk(tokens[0].strip("-–—:|[]()")):
        tokens.pop(0)
    while tokens and _looks_like_junk(tokens[-1].strip("-–—:|[]()")):
        tokens.pop()
    text = " ".join(tokens)

    text = _SEPARATOR.sub(" ", text).strip(" \t\r\n-–—:|")
    return text.strip()


def sanitize_lookup_title(value: str | None) -> str:
    return sanitize_lookup_text(value)


def sanitize_lookup_artist(value: str | None) -> str:
    return sanitize_lookup_text(value)
