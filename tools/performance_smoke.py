"""Reproducible v0.14 large-library smoke benchmark.

Wall-clock values are observational and are not used as tight CI gates. The report
also contains deterministic work metrics; invariant violations fail the command.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any

from musicark.local_library.models import LocalLibraryRoot, LocalTrackMetadata
from musicark.local_library.scanner import LocalLibraryScanner
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import (
    LocalLibraryStorageRepository,
    normalize_local_path,
)

DATASET_SIZES = (1_000, 10_000, 50_000)
PAGE_SIZE = 250
FILESYSTEM_DATASET_SIZE = 5_000


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


def _query_plan(db_path: Path, *, search: bool, root_id: int | None = None) -> list[str]:
    where = "availability='available' AND library_root_id IS NOT NULL"
    params: list[Any] = []
    if root_id is not None:
        where += " AND library_root_id=?"
        params.append(root_id)
    if search:
        where += (
            " AND (title LIKE ? COLLATE NOCASE OR artists_json LIKE ? COLLATE NOCASE "
            "OR COALESCE(album,'') LIKE ? COLLATE NOCASE OR file_name LIKE ? COLLATE NOCASE)"
        )
        params.extend(["%Needle%"] * 4)
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
        self.seen = 0
        self.allow_removals = False

    def file_states(self, root_id: int) -> dict[str, dict[str, Any]]:
        return self.states

    def apply_scan(
        self,
        root_id: int,
        *,
        upserts,
        seen_normalized_paths,
        missing_normalized_paths=None,
        allow_removals: bool,
        **kwargs,
    ) -> int:
        self.upserts = len(list(upserts))
        self.missing = len(set(missing_normalized_paths or ()))
        self.seen = len(set(seen_normalized_paths))
        self.allow_removals = allow_removals
        return self.missing if allow_removals else 0


class _CountingMetadataReader:
    def __init__(self, *, allow_reads: bool = False) -> None:
        self.calls = 0
        self._allow_reads = allow_reads

    def read(self, path: Path) -> LocalTrackMetadata:
        self.calls += 1
        if not self._allow_reads:
            raise AssertionError("unchanged synthetic files must not be parsed")
        return LocalTrackMetadata(
            title=path.stem,
            artists=("Synthetic Artist",),
            album="Synthetic Album",
            duration_seconds=180.0,
            codec=path.suffix.lstrip("."),
            container=path.suffix.lstrip("."),
        )


def _root(path: Path) -> LocalLibraryRoot:
    return LocalLibraryRoot(
        id=1,
        path=str(path),
        normalized_path=normalize_local_path(path),
        enabled=True,
        created_at="2026-08-21T00:00:00Z",
    )


def _snapshot_files(root_path: Path, count: int) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for index in range(count):
        suffix = (".mp3", ".flac", ".m4a", ".ogg", ".opus")[index % 5]
        path = root_path / f"трек {index:05d}{suffix}"
        path.touch()
        stat = path.stat()
        states[normalize_local_path(path)] = {
            "id": index + 1,
            "file_size": int(stat.st_size),
            "modified_ns": int(stat.st_mtime_ns),
            "sha256": "",
        }
    return states


def _unchanged_scan_metrics(file_count: int = 1_000) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root_path = Path(tmp) / "Музыка с пробелами"
        root_path.mkdir()
        states = _snapshot_files(root_path, file_count)
        repository = _ScanRepository(states)
        reader = _CountingMetadataReader()
        scanner = LocalLibraryScanner(repository, metadata_reader=reader)  # type: ignore[arg-type]
        result, elapsed = _elapsed_ms(lambda: scanner.scan(_root(root_path)))
        metrics = {
            "files": file_count,
            "unchangedScanMs": elapsed,
            "scanMetadataReads": reader.calls,
            "scanDatabaseUpserts": repository.upserts,
            "scanMissingPaths": repository.missing,
            "seenPaths": repository.seen,
            "unchanged": result.unchanged,
        }
        if reader.calls != 0 or repository.upserts != 0 or repository.missing != 0:
            raise RuntimeError(f"unchanged scan regression: {metrics}")
        if result.unchanged != file_count:
            raise RuntimeError(f"unchanged count regression: {metrics}")
        return metrics


def _delta_scan_metrics(file_count: int = FILESYSTEM_DATASET_SIZE) -> dict[str, Any]:
    added_count = 5
    changed_count = 7
    removed_count = 3
    with tempfile.TemporaryDirectory() as tmp:
        root_path = Path(tmp) / "Music Delta"
        root_path.mkdir()
        states = _snapshot_files(root_path, file_count)
        paths_by_state = {normalized: Path(str(normalized)) for normalized in states}

        # Resolve real paths from the normalized snapshot deterministically.
        real_paths = sorted(root_path.iterdir(), key=lambda path: path.name)
        for path in real_paths[:removed_count]:
            path.unlink()
        for path in real_paths[removed_count:removed_count + changed_count]:
            before = path.stat().st_mtime_ns
            path.write_bytes(b"changed")
            os.utime(path, ns=(before + 2_000_000_000, before + 2_000_000_000))
        for index in range(added_count):
            (root_path / f"new {index:02d}.flac").write_bytes(b"new")

        repository = _ScanRepository(states)
        reader = _CountingMetadataReader(allow_reads=True)
        scanner = LocalLibraryScanner(repository, metadata_reader=reader)  # type: ignore[arg-type]
        result, elapsed = _elapsed_ms(lambda: scanner.scan(_root(root_path)))
        expected_reads = added_count + changed_count
        expected_unchanged = file_count - removed_count - changed_count
        metrics = {
            "filesBefore": file_count,
            "addedExpected": added_count,
            "changedExpected": changed_count,
            "removedExpected": removed_count,
            "deltaScanMs": elapsed,
            "scanMetadataReads": reader.calls,
            "scanDatabaseUpserts": repository.upserts,
            "scanMissingPaths": repository.missing,
            "resultAdded": result.added,
            "resultUpdated": result.updated,
            "resultRemoved": result.removed,
            "resultUnchanged": result.unchanged,
        }
        if reader.calls != expected_reads or repository.upserts != expected_reads:
            raise RuntimeError(f"delta scan work is not proportional to delta: {metrics}")
        if repository.missing != removed_count or result.removed != removed_count:
            raise RuntimeError(f"delta removal regression: {metrics}")
        if result.added != added_count or result.updated != changed_count:
            raise RuntimeError(f"delta classification regression: {metrics}")
        if result.unchanged != expected_unchanged:
            raise RuntimeError(f"delta unchanged regression: {metrics}")
        return metrics


def _validate_dataset(
    *,
    count: int,
    root_id: int,
    first_page: list[dict[str, Any]],
    second_page: list[dict[str, Any]],
    scoped_first: list[dict[str, Any]],
    scoped_second: list[dict[str, Any]],
    search: list[dict[str, Any]],
    total: int,
    search_total: int,
    root_total: int,
) -> None:
    for label, rows in (
        ("first", first_page),
        ("second", second_page),
        ("scoped-first", scoped_first),
        ("scoped-second", scoped_second),
        ("search", search),
    ):
        if len(rows) > PAGE_SIZE:
            raise RuntimeError(f"{label} page materialized {len(rows)} > {PAGE_SIZE}")
    if total != count:
        raise RuntimeError(f"dataset count mismatch: expected {count}, got {total}")
    expected_search = ((count - 1) // 997) + 1 if count else 0
    if search_total != expected_search:
        raise RuntimeError(
            f"search count mismatch for {count}: expected {expected_search}, got {search_total}"
        )
    expected_root_total = (count + 1) // 3
    if root_total != expected_root_total:
        raise RuntimeError(
            f"root count mismatch for {count}: expected {expected_root_total}, got {root_total}"
        )
    if any("Needle" not in str(row.get("title", "")) for row in search):
        raise RuntimeError("search returned a row outside the query scope")
    if any(int(row.get("rootId") or -1) != root_id for row in (*scoped_first, *scoped_second)):
        raise RuntimeError("root-filtered pagination leaked a row from another root")
    first_ids = {int(row["id"]) for row in first_page}
    second_ids = {int(row["id"]) for row in second_page}
    if first_ids.intersection(second_ids):
        raise RuntimeError("adjacent global pages contain duplicate rows")
    scoped_first_ids = {int(row["id"]) for row in scoped_first}
    scoped_second_ids = {int(row["id"]) for row in scoped_second}
    if scoped_first_ids.intersection(scoped_second_ids):
        raise RuntimeError("adjacent scoped pages contain duplicate rows")


def benchmark_dataset(count: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "musicark.db"
        initialize_database(db_path)
        root_ids = _insert_synthetic(db_path, count)
        repository = LocalLibraryStorageRepository(db_path)

        (page, total), page_ms = _elapsed_ms(
            lambda: repository.list_tracks(limit=PAGE_SIZE, offset=0, sort="title")
        )
        second_page, second_total = repository.list_tracks(
            limit=PAGE_SIZE,
            offset=PAGE_SIZE,
            sort="title",
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
        scoped_second, scoped_second_total = repository.list_tracks(
            limit=PAGE_SIZE,
            offset=PAGE_SIZE,
            search="Track",
            sort="album",
            root_ids=[root_ids[1]],
        )
        scoped_first, scoped_total = repository.list_tracks(
            limit=PAGE_SIZE,
            offset=0,
            search="Track",
            sort="album",
            root_ids=[root_ids[1]],
        )
        (tail, tail_total), tail_ms = _elapsed_ms(
            lambda: repository.list_tracks(
                limit=PAGE_SIZE,
                offset=max(0, count - PAGE_SIZE),
                sort="original",
            )
        )

        if second_total != count or tail_total != count:
            raise RuntimeError("pagination count changed across offsets")
        if scoped_total != root_total or scoped_second_total != root_total:
            raise RuntimeError("root/search/sort scope changed across pages")
        _validate_dataset(
            count=count,
            root_id=root_ids[1],
            first_page=page,
            second_page=second_page,
            scoped_first=scoped_first,
            scoped_second=scoped_second,
            search=search,
            total=total,
            search_total=search_total,
            root_total=root_total,
        )

        return {
            "dataset": count,
            "localQueryMs": page_ms,
            "localSearchMs": search_ms,
            "rootFilterMs": root_ms,
            "tailOffsetMs": tail_ms,
            "rowsMaterialized": len(page),
            "secondPageRowsMaterialized": len(second_page),
            "searchRowsMaterialized": len(search),
            "rootRowsMaterialized": len(root_page),
            "scopedFirstRowsMaterialized": len(scoped_first),
            "scopedSecondRowsMaterialized": len(scoped_second),
            "tailRowsMaterialized": len(tail),
            "totalRows": total,
            "searchTotal": search_total,
            "rootTotal": root_total,
            "queryPlan": _query_plan(db_path, search=False),
            "searchQueryPlan": _query_plan(db_path, search=True),
            "rootQueryPlan": _query_plan(db_path, search=False, root_id=root_ids[1]),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=int, action="append", choices=DATASET_SIZES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sizes = tuple(args.dataset or DATASET_SIZES)
    payload = {
        "schema": 2,
        "pageSize": PAGE_SIZE,
        "datasets": [benchmark_dataset(size) for size in sizes],
        "unchangedScan": _unchanged_scan_metrics(),
        "deltaScan": _delta_scan_metrics(),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
