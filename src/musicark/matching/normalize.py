"""Deterministic, conservative text normalization for local matching."""

from __future__ import annotations

from collections.abc import Iterable
import re
import unicodedata

_DASH_TRANSLATION = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
})
_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)
_ARTIST_SEPARATOR = re.compile(
    r"\s*(?:,|;|&|\+|\bx\b|\bfeat(?:uring)?\.?\b|\bft\.?\b)\s*",
    re.IGNORECASE,
)
_VERSION_MARKERS = frozenset(
    {
        "live",
        "remix",
        "acoustic",
        "instrumental",
        "remaster",
        "remastered",
        "demo",
        "radio",
        "edit",
        "extended",
        "mix",
    }
)


def normalize_text(value: str | None) -> str:
    """Normalize presentation differences without deleting semantic words.

    The function intentionally keeps words such as ``live``/``remix``/``acoustic``.
    Punctuation and dash variants become token boundaries rather than being interpreted.
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).translate(_DASH_TRANSLATION).casefold()
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def split_artists(value: str | None) -> tuple[str, ...]:
    """Split common artist-list spellings and return normalized names."""
    if not value:
        return ()
    parts = _ARTIST_SEPARATOR.split(str(value))
    normalized = [normalize_text(part) for part in parts]
    return tuple(part for part in normalized if part)


def normalize_artists(values: Iterable[str] | str | None) -> tuple[str, ...]:
    """Normalize an artist collection as an order-independent, de-duplicated tuple."""
    if values is None:
        return ()
    raw_values: Iterable[str]
    if isinstance(values, str):
        raw_values = (values,)
    else:
        raw_values = values
    names: set[str] = set()
    for value in raw_values:
        names.update(split_artists(value))
    return tuple(sorted(names))


def artists_key(values: Iterable[str] | str | None) -> str:
    """Stable indexed representation for an order-independent artist set."""
    return "|".join(normalize_artists(values))


def title_version_markers(value: str | None) -> frozenset[str]:
    """Return meaningful version markers preserved by normalization."""
    return frozenset(token for token in normalize_text(value).split() if token in _VERSION_MARKERS)
