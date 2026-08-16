"""Download-specific matching freshness maintenance.

A normal Local Library mutation invalidates automatic matching results through the
v0.5 global library fingerprint. An exact provider download is different: MusicArk
knows the single added file and immediately binds it to the exact provider identity.
Rebase only results that were fresh immediately before that controlled mutation so
one download does not turn every unrelated Missing row into Not Analyzed.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError


def rebase_after_exact_download(
    database_path: Path,
    *,
    previous_fingerprint: str,
    current_fingerprint: str,
    provider_id: str,
    external_id: str,
) -> int:
    """Move previously-fresh automatic results to the new library fingerprint.

    Only rows whose fingerprint exactly equals ``previous_fingerprint`` are touched.
    Results that were already stale therefore remain stale. The newly downloaded
    identity is excluded because its new exact MatchDecision is persisted separately
    with ``current_fingerprint``.
    """

    previous = str(previous_fingerprint or "").strip()
    current = str(current_fingerprint or "").strip()
    if not previous or not current or previous == current:
        return 0

    try:
        with closing(sqlite3.connect(database_path)) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE matching_results
                    SET local_fingerprint=?
                    WHERE COALESCE(manual, 0)=0
                      AND local_fingerprint=?
                      AND NOT (provider_id=? AND external_id=?)
                    """,
                    (current, previous, provider_id, external_id),
                )
                return max(0, int(cursor.rowcount))
    except sqlite3.Error as exc:
        raise StorageError(
            "Failed to preserve matching freshness after exact download."
        ) from exc
