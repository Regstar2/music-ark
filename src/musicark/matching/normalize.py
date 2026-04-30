"""Normalization helpers for matching-engine."""

from __future__ import annotations

import re
import unicodedata


_NON_ALNUM = re.compile(r"[^a-z0-9а-я]+", re.IGNORECASE)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value).lower()
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(text.split())


def split_artists(value: str) -> tuple[str, ...]:
    parts = re.split(r",|&| feat\. | ft\. | x ", value, flags=re.IGNORECASE)
    normalized = [normalize_text(part) for part in parts]
    return tuple(part for part in normalized if part)
