"""Reproducible v0.14 large-library smoke benchmark.

Wall-clock values are observational and are not used as tight CI gates. The report
also contains deterministic work metrics used by regression tests.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any

from musicark.local_library.models import LocalLibraryRoot
from musicark.local_library.scanner import LocalLibraryScanner
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import (
    LocalLibraryStorageRepository,
    normalize_local_path,
)

DATASET_SIZES = (1_000, 10_000, 50_000)
PAGE_SIZE = 250


def _elapsed_ms(callable_: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    value = callable_()
    return value, round((time.perf_counter() - started) * 1000.0, 3)


def _insert_synthetic(db_path: Path, count: int) -> list[int]:
    roots = [
        ("C:/Music/Primary", "c:/music/primary"),
        ("D:/Музыка/Archive", "d:/музыка/archive"),
        ("E:/Music With Spaces/Mixed", "e:/music with spaces/mixed"),
    ]
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executemany(
                "INSERT INTO local_library_roots(path, normalized_path) VALUES (?, ?)",
                roots,
            )
            root_ids = [
                int(row[0])
                for row in conn.execute(
                    "SELECT id FROM local_library_roots ORDER BY id"
                ).fetchall()
            ]
            formats = (".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav")
            rows: list[tuple[Any, ...]] = []
            for index in range(count):
                root_id = root_ids[index % len(root_ids)]
                extension = formats[index % len(formats)]
                needle = " Needle" if index % 997 == 0 else ""
                title = f"Track {index:06d}{needle}"
                artist = f"Artist {index % 173:03d}"
                album = f"Album {index % 257:03d}"
                path = f"{roots[index % len(roots)][0]}/{artist}/{album}/{title}{extension}"
                rows.append(
                    (
                        root_id,
                        path,
                        path.replace("\\", "/").casefold(),
                        f"{title}{extension}",
                        extension,
                        "",
                        1_000_000 + index,
                        1_700_000_000_000_000_000 + index,
                        180.0 + (index % 120),
                        extension.lstrip("."),
                        "{}",
                        title,
                        json.dumps([artist], ensure_ascii=False),
                        album,
                        "available",
                    )
                )
                if len(rows) >= 2_000:
                    conn.executemany(
                        """
                        INSERT INTO local_audio_files(
                            library_root_id, path, normalized_path, file_name, extension,
                            sha256, file_size, modified_ns, duration_seconds, codec,
                            metadata_json, title, artists_json, album, availability
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                    rows.clear()
            if rows:
                conn.executemany(
                    """
                    INSERT INTO local_audio_files(
                        library_root_id, path, normalized_path, file_name, extension,
                        sha256, file_size, modified_ns, duration_seconds, codec,
                        metadata_json, title, artists_json, album, availability
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
    return root_ids


def _query_plan(db_path: Path, *, search: bool) -> list[str]:
    where = "availability='available' AND library_root_id IS NOT NULL"
    params: list[Any] = []
    if search:
        where += " AND (title LIKE ? COLLATE NOCASE OR artists_json LIKE ? COLLATE NOCASE OR COALESCE(album,'') LIKE ? COLLATE NOCASE OR file_name LIKE ? COLLATE NOCASE)"
        params = ["%Needle%"] * 4
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            f"""
            EXPLAIN QUERY PLAN
            SELECT id, title FROM local_audio_files
            WHERE {where}
            ORDER BY title COLLATE NOCASE, path COLLATE NOCASE
            LIMIT 250 OFFSET 0
            """,
            params,
        ).fetchall()
    return [str(row[3]) for row in rows]


class _ScanRepository:
    def __init__(self, states: dict[str, dict[str, Any]]) -> None:
        self.states = states
        self.upserts = 0
        self.missing = 0

    def file_states(self, root_id: int) -> dict[str, dict[str, Any]]:
        return self.states

    def apply_scan(self, root_id: int, *, upserts, missing_normalized_paths=None, **kwargs) -> int:  # type: ignore[no-untyped-def]
        self.upserts = len(list(upserts))
        self.missing = len(set(missing_normalized_paths or ()))
        return self.missing


class _CountingMetadataReader:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, path: Path):  # pragma: no cover - unchanged scan must not call it.
        self.calls += 1
        raise AssertionError("unchanged synthetic files must not be parsed")


def _unchanged_scan_metrics(file_count: int = 1_000) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root_path = Path(tmp) / "scan"
        root_path.mkdir()
        states: dict[str, dict[str, Any]] = {}
        for index in range(file_count):
            path = root_path / f"track-{index:05d}.mp3"
            path.touch()
            stat = path.stat()
            states[normalize_local_path(path)] = {
                "id": index + 1,
                "file_size": int(stat.st_size),
                "modified_ns": int(stat.st_mtime_ns),
                "sha256": "",
            }
        repository = _ScanRepository(states)
        reader = _CountingMetadataReader()
        scanner = LocalLibraryScanner(repository, metadata_reader=reader)  # type: ignore[arg-type]
        root = LocalLibraryRoot(
            id=1,
            path=str(root_path),
            normalized_path=normalize_local_path(root_path),
            enabled=True,
            created_at="2026-08-21T00:00:00Z",
        )
        result, elapsed = _elapsed_ms(lambda: scanner.scan(root))
        return {
            "files": file_count,
            "unchangedScanMs": elapsed,
            "scanMetadataReads": reader.calls,
            "scanDatabaseUpserts": repository.upserts,
            "scanMissingPaths": repository.missing,
            "unchanged": result.unchanged,
        }


def benchmark_dataset(count: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "musicark.db"
        initialize_database(db_path)
        root_ids = _insert_synthetic(db_path, count)
        repository = LocalLibraryStorageRepository(db_path)

        (page, total), page_ms = _elapsed_ms(
            lambda: repository.list_tracks(limit=PAGE_SIZE, offset=0, sort="title")
        )
        (search, search_total), search_ms = _elapsed_ms(
            lambda: repository.list_tracks(
                limit=PAGE_SIZE, offset=0, search="Needle", sort="title"
            )
        )
        (root_page, root_total), root_ms = _elapsed_ms(
            lambda: repository.list_tracks(
                limit=PAGE_SIZE,
                offset=0,
                sort="artist",
                root_ids=[root_ids[1]],
            )
        )
        (tail, _), tail_ms = _elapsed_ms(
            lambda: repository.list_tracks(
                limit=PAGE_SIZE,
                offset=max(0, count - PAGE_SIZE),
                sort="original",
            )
        )
        return {
            "dataset": count,
            "localQueryMs": page_ms,
            "localSearchMs": search_ms,
            "rootFilterMs": root_ms,
            "tailOffsetMs": tail_ms,
            "rowsMaterialized": len(page),
            "searchRowsMaterialized": len(search),
            "rootRowsMaterialized": len(root_page),
            "tailRowsMaterialized": len(tail),
            "totalRows": total,
            "searchTotal": search_total,
            "rootTotal": root_total,
            "queryPlan": _query_plan(db_path, search=False),
            "searchQueryPlan": _query_plan(db_path, search=True),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=int, action="append", choices=DATASET_SIZES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sizes = tuple(args.dataset or DATASET_SIZES)
    payload = {
        "schema": 1,
        "pageSize": PAGE_SIZE,
        "datasets": [benchmark_dataset(size) for size in sizes],
        "unchangedScan": _unchanged_scan_metrics(),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
