"""Persistent user triage actions for Library Coverage."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError

_ALLOWED_ACTIONS = {"wanted", "ignored", "unreviewed"}


class CoverageActionStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def set_action(
        self,
        *,
        provider_id: str,
        external_id: str,
        action: str,
    ) -> str:
        clean_action = action.strip().casefold()
        if clean_action not in _ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported coverage action: {action}")
        if not self._identity_is_active(provider_id, external_id):
            raise ValueError(
                f"Provider track {provider_id}:{external_id} is not in the active library."
            )
        try:
            with closing(self._connect()) as conn:
                with conn:
                    if clean_action == "unreviewed":
                        conn.execute(
                            "DELETE FROM provider_track_actions "
                            "WHERE provider_id=? AND external_id=?",
                            (provider_id, external_id),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO provider_track_actions(
                                provider_id, external_id, action
                            ) VALUES (?, ?, ?)
                            ON CONFLICT(provider_id, external_id) DO UPDATE SET
                                action=excluded.action,
                                updated_at=datetime('now')
                            """,
                            (provider_id, external_id, clean_action),
                        )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist Library Coverage action.") from exc
        return clean_action

    def set_actions(
        self,
        *,
        provider_id: str,
        external_ids: Iterable[str],
        action: str,
    ) -> dict[str, Any]:
        clean_ids = list(
            dict.fromkeys(
                str(item).strip() for item in external_ids if str(item).strip()
            )
        )
        if len(clean_ids) > 5000:
            raise ValueError("At most 5000 provider tracks can be updated at once.")
        clean_action = action.strip().casefold()
        if clean_action not in _ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported coverage action: {action}")
        if not clean_ids:
            return {"updated": 0, "action": clean_action}

        active = self._active_identity_subset(provider_id, clean_ids)
        if len(active) != len(clean_ids):
            missing = next(item for item in clean_ids if item not in active)
            raise ValueError(
                f"Provider track {provider_id}:{missing} is not in the active library."
            )

        try:
            with closing(self._connect()) as conn:
                with conn:
                    if clean_action == "unreviewed":
                        conn.executemany(
                            "DELETE FROM provider_track_actions "
                            "WHERE provider_id=? AND external_id=?",
                            ((provider_id, external_id) for external_id in clean_ids),
                        )
                    else:
                        conn.executemany(
                            """
                            INSERT INTO provider_track_actions(
                                provider_id, external_id, action
                            ) VALUES (?, ?, ?)
                            ON CONFLICT(provider_id, external_id) DO UPDATE SET
                                action=excluded.action,
                                updated_at=datetime('now')
                            """,
                            (
                                (provider_id, external_id, clean_action)
                                for external_id in clean_ids
                            ),
                        )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist bulk Library Coverage actions.") from exc

        return {"updated": len(clean_ids), "action": clean_action}

    def _identity_is_active(self, provider_id: str, external_id: str) -> bool:
        return external_id in self._active_identity_subset(provider_id, [external_id])

    def _active_identity_subset(
        self, provider_id: str, external_ids: list[str]
    ) -> set[str]:
        if not external_ids:
            return set()
        placeholders = ",".join("?" for _ in external_ids)
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT
                        CASE
                            WHEN json_valid(pci.payload_json)
                            THEN COALESCE(
                                NULLIF(CAST(json_extract(
                                    pci.payload_json, '$.external_id'
                                ) AS TEXT), ''),
                                pci.external_id
                            )
                            ELSE pci.external_id
                        END
                    FROM provider_collection_items pci
                    JOIN provider_collection_snapshots pcs
                      ON pcs.provider_id=pci.provider_id
                     AND pcs.collection_id=pci.collection_id
                    WHERE pci.provider_id=?
                      AND pcs.active=1
                      AND CASE
                            WHEN json_valid(pci.payload_json)
                            THEN COALESCE(
                                NULLIF(CAST(json_extract(
                                    pci.payload_json, '$.external_id'
                                ) AS TEXT), ''),
                                pci.external_id
                            )
                            ELSE pci.external_id
                          END IN ({placeholders})
                    """,
                    [provider_id, *external_ids],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to validate active provider identities.") from exc
        return {str(row[0]) for row in rows}
