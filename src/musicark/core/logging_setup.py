"""Logging setup utilities for MusicArk core."""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger for CLI and core services."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
