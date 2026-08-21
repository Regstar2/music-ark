from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual < count:
        raise RuntimeError(f"{path}: expected at least {count} occurrence(s), found {actual}: {old[:80]!r}")
    text = text.replace(old, new, count)
    file.write_text(text, encoding="utf-8")


def regex_replace(path: str, pattern: str, replacement: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: regex replacement count was {count}")
    file.write_text(updated, encoding="utf-8")


# Backend hard page bound lives in the v0.12 service base reused by v0.13/v0.14.
replace(
    "src/musicark/local_library/_service_v012.py",
    "page_limit = max(1, min(int(limit), 5000))",
    "page_limit = max(1, min(int(limit), 250))",
)

# Delta-only scan persistence. Legacy callers can still omit missing_normalized_paths.
regex_replace(
    "src/musicark/storage/local_library_storage.py",
    r"    def apply_scan\(\n.*?\n    @staticmethod\n    def _record_tuple",
    '''    def apply_scan(\n        self,\n        root_id: int,\n        *,\n        upserts: Iterable[LocalAudioRecord],\n        seen_normalized_paths: set[str],\n        scanned_at: str,\n        allow_removals: bool,\n        missing_normalized_paths: Iterable[str] | None = None,\n    ) -> int:\n        \"\"\"Persist scan deltas without rewriting every unchanged library row.\n\n        New scanners pass the missing-path delta computed from the pre-scan\n        snapshot. ``None`` preserves the legacy seen-set path for compatibility.\n        \"\"\"\n        rows = [self._record_tuple(item, scanned_at) for item in upserts]\n        missing = (\n            None\n            if missing_normalized_paths is None\n            else list(dict.fromkeys(str(path) for path in missing_normalized_paths))\n        )\n        removed = 0\n        try:\n            with closing(sqlite3.connect(self._database_path)) as conn:\n                with conn:\n                    if rows:\n                        conn.executemany(\n                            \"\"\"\n                            INSERT INTO local_audio_files(\n                                library_root_id, path, normalized_path, file_name, extension,\n                                sha256, file_size, modified_ns, duration_seconds, codec,\n                                metadata_json, title, artists_json, album, album_artist,\n                                track_number, disc_number, year, genre, bitrate, sample_rate,\n                                availability, last_seen_at\n                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'available',?)\n                            ON CONFLICT(normalized_path) DO UPDATE SET\n                                library_root_id=excluded.library_root_id,\n                                path=excluded.path,\n                                file_name=excluded.file_name,\n                                extension=excluded.extension,\n                                sha256=excluded.sha256,\n                                file_size=excluded.file_size,\n                                modified_ns=excluded.modified_ns,\n                                duration_seconds=excluded.duration_seconds,\n                                codec=excluded.codec,\n                                metadata_json=excluded.metadata_json,\n                                title=excluded.title,\n                                artists_json=excluded.artists_json,\n                                album=excluded.album,\n                                album_artist=excluded.album_artist,\n                                track_number=excluded.track_number,\n                                disc_number=excluded.disc_number,\n                                year=excluded.year,\n                                genre=excluded.genre,\n                                bitrate=excluded.bitrate,\n                                sample_rate=excluded.sample_rate,\n                                availability='available',\n                                last_seen_at=excluded.last_seen_at,\n                                updated_at=datetime('now')\n                            \"\"\",\n                            rows,\n                        )\n\n                    if missing is None:\n                        conn.execute(\n                            \"CREATE TEMP TABLE IF NOT EXISTS local_scan_seen(path TEXT PRIMARY KEY)\"\n                        )\n                        conn.execute(\"DELETE FROM local_scan_seen\")\n                        if seen_normalized_paths:\n                            conn.executemany(\n                                \"INSERT OR IGNORE INTO local_scan_seen(path) VALUES (?)\",\n                                ((path,) for path in seen_normalized_paths),\n                            )\n                        conn.execute(\n                            \"\"\"\n                            UPDATE local_audio_files\n                            SET last_seen_at=?\n                            WHERE library_root_id=?\n                              AND normalized_path IN (SELECT path FROM local_scan_seen)\n                            \"\"\",\n                            (scanned_at, int(root_id)),\n                        )\n                        if allow_removals:\n                            cursor = conn.execute(\n                                \"\"\"\n                                DELETE FROM local_audio_files\n                                WHERE library_root_id=?\n                                  AND normalized_path NOT IN (SELECT path FROM local_scan_seen)\n                                \"\"\",\n                                (int(root_id),),\n                            )\n                            removed = max(0, int(cursor.rowcount))\n                    elif allow_removals and missing:\n                        for offset in range(0, len(missing), 400):\n                            batch = missing[offset:offset + 400]\n                            placeholders = \",\".join(\"?\" for _ in batch)\n                            cursor = conn.execute(\n                                f\"\"\"\n                                DELETE FROM local_audio_files\n                                WHERE library_root_id=?\n                                  AND normalized_path IN ({placeholders})\n                                \"\"\",\n                                [int(root_id), *batch],\n                            )\n                            removed += max(0, int(cursor.rowcount))\n\n                    conn.execute(\n                        \"UPDATE local_library_roots SET last_scanned_at=? WHERE id=?\",\n                        (scanned_at, int(root_id)),\n                    )\n        except sqlite3.Error as exc:\n            raise StorageError(\"Failed to persist local library scan.\") from exc\n        return removed\n\n    @staticmethod\n    def _record_tuple''',
)

# Local Library: cache-first open, 250-row page, stale async protection.
replace("ui/musicark_ui/lib/local_library_page.dart", "static const _pageSize = 500;", "static const _pageSize = 250;")
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "  bool _statusIsError = false;\n  String? _error;",
    "  bool _statusIsError = false;\n  String? _error;\n  int _requestGeneration = 0;",
)
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "  Future<void> _activate() async {\n    await _reload();\n    if (!mounted || _roots.isEmpty) return;\n    await _scan();\n  }",
    "  Future<void> _activate() async {\n    // Opening Local Library is cache-first. Filesystem traversal is explicit.\n    await _reload();\n  }",
)
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "  Future<void> _reload({bool preserveStatus = false}) async {\n    setState(() {",
    "  Future<void> _reload({bool preserveStatus = false}) async {\n    final generation = ++_requestGeneration;\n    setState(() {",
)
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "      tracks = await _withContentLabels(tracks);\n      if (!mounted) return;",
    "      tracks = await _withContentLabels(tracks);\n      if (!mounted || generation != _requestGeneration) return;",
)
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "  Future<void> _loadMore() async {\n    if (_tracks.length >= _total || _busy) return;\n    setState(() => _busy = true);",
    "  Future<void> _loadMore() async {\n    if (_tracks.length >= _total || _busy) return;\n    final generation = _requestGeneration;\n    setState(() => _busy = true);",
)
replace(
    "ui/musicark_ui/lib/local_library_page.dart",
    "      items = await _withContentLabels(items);\n      if (!mounted) return;",
    "      items = await _withContentLabels(items);\n      if (!mounted || generation != _requestGeneration) return;",
)

# Yandex workspace: debounce/memoization/lazy fixed rows/bounded image decode.
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "import 'package:flutter/material.dart';",
    "import 'dart:async';\n\nimport 'package:flutter/material.dart';",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "class _MusicArkHomePageState extends State<MusicArkHomePage> {\n  final _tokenController",
    "class _MusicArkHomePageState extends State<MusicArkHomePage> {\n  static const _trackSearchDelay = Duration(milliseconds: 180);\n\n  final _tokenController",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "  _PageKind _page = _PageKind.liked;",
    "  _PageKind _page = _PageKind.liked;\n  Timer? _trackSearchDebounce;\n  String _trackSearchQuery = '';\n  List<Map<String, dynamic>>? _visibleTrackCache;\n  List<Map<String, dynamic>>? _visibleTrackCacheSource;\n  String _visibleTrackCacheQuery = '';\n  LibrarySort? _visibleTrackCacheSort;",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "  void dispose() {\n    _tokenController.dispose();",
    "  void dispose() {\n    _trackSearchDebounce?.cancel();\n    _tokenController.dispose();",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "  Future<void> _initialize() async {",
    '''  void _invalidateVisibleTracks() {\n    _visibleTrackCache = null;\n    _visibleTrackCacheSource = null;\n    _visibleTrackCacheQuery = '';\n    _visibleTrackCacheSort = null;\n  }\n\n  void _resetTrackSearch() {\n    _trackSearchDebounce?.cancel();\n    _searchController.clear();\n    _trackSearchQuery = '';\n    _invalidateVisibleTracks();\n  }\n\n  void _scheduleTrackSearch(String value) {\n    final query = value.trim().toLowerCase();\n    _trackSearchDebounce?.cancel();\n    _trackSearchDebounce = Timer(_trackSearchDelay, () {\n      if (!mounted || query == _trackSearchQuery) return;\n      setState(() {\n        _trackSearchQuery = query;\n        _invalidateVisibleTracks();\n      });\n    });\n  }\n\n  void _submitTrackSearch(String value) {\n    final query = value.trim().toLowerCase();\n    _trackSearchDebounce?.cancel();\n    if (query == _trackSearchQuery) return;\n    setState(() {\n      _trackSearchQuery = query;\n      _invalidateVisibleTracks();\n    });\n  }\n\n  Future<void> _initialize() async {''',
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "      _albumsLastUpdated = albums['lastUpdated']?.toString();\n      _errorMessage = null;",
    "      _albumsLastUpdated = albums['lastUpdated']?.toString();\n      _invalidateVisibleTracks();\n      _errorMessage = null;",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "      _page = _PageKind.playlist;\n      _searchController.clear();\n      _trackSort = LibrarySort.original;",
    "      _page = _PageKind.playlist;\n      _resetTrackSearch();\n      _trackSort = LibrarySort.original;",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "      _page = _PageKind.album;\n      _searchController.clear();\n      _trackSort = LibrarySort.original;",
    "      _page = _PageKind.album;\n      _resetTrackSearch();\n      _trackSort = LibrarySort.original;",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "      _detailLastUpdated = collection['lastUpdated']?.toString();\n      _errorMessage = null;",
    "      _detailLastUpdated = collection['lastUpdated']?.toString();\n      _invalidateVisibleTracks();\n      _errorMessage = null;",
)
regex_replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    r"  void _showLiked\(\) => setState\(\(\) \{.*?\n  List<Map<String, dynamic>> get _trackSource =>",
    '''  void _showLiked() {\n    setState(() {\n      _page = _PageKind.liked;\n      _resetTrackSearch();\n      _trackSort = LibrarySort.original;\n    });\n  }\n\n  void _showPlaylists() {\n    _trackSearchDebounce?.cancel();\n    setState(() {\n      _page = _PageKind.playlists;\n      _searchController.clear();\n      _trackSearchQuery = '';\n      _invalidateVisibleTracks();\n      _playlistSort = PlaylistSort.original;\n    });\n  }\n\n  void _showAlbums() {\n    _trackSearchDebounce?.cancel();\n    setState(() {\n      _page = _PageKind.albums;\n      _searchController.clear();\n      _trackSearchQuery = '';\n      _invalidateVisibleTracks();\n    });\n  }\n\n  List<Map<String, dynamic>> get _trackSource =>''',
)
regex_replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    r"  List<Map<String, dynamic>> get _visibleTracks \{.*?\n  List<Map<String, dynamic>> get _visiblePlaylists \{",
    '''  List<Map<String, dynamic>> get _visibleTracks {\n    final source = _trackSource;\n    final query = _trackSearchQuery;\n    if (query.isEmpty && _trackSort == LibrarySort.original) return source;\n    if (identical(_visibleTrackCacheSource, source) &&\n        _visibleTrackCacheQuery == query &&\n        _visibleTrackCacheSort == _trackSort &&\n        _visibleTrackCache != null) {\n      return _visibleTrackCache!;\n    }\n\n    final filtered = query.isEmpty\n        ? source.toList(growable: false)\n        : source.where((track) {\n            return '${track['title'] ?? ''} ${_artists(track)} ${track['album_title'] ?? ''}'\n                .toLowerCase()\n                .contains(query);\n          }).toList(growable: false);\n    final indexed = filtered.asMap().entries.toList();\n    switch (_trackSort) {\n      case LibrarySort.original:\n        break;\n      case LibrarySort.title:\n        indexed.sort((a, b) {\n          final result = _title(a.value)\n              .toLowerCase()\n              .compareTo(_title(b.value).toLowerCase());\n          return result == 0 ? a.key.compareTo(b.key) : result;\n        });\n      case LibrarySort.artist:\n        indexed.sort((a, b) {\n          final result = _artists(a.value)\n              .toLowerCase()\n              .compareTo(_artists(b.value).toLowerCase());\n          return result == 0 ? a.key.compareTo(b.key) : result;\n        });\n      case LibrarySort.unavailable:\n        indexed.sort((a, b) {\n          final aUnavailable = '${a.value['availability'] ?? ''}' == 'unavailable';\n          final bUnavailable = '${b.value['availability'] ?? ''}' == 'unavailable';\n          if (aUnavailable != bUnavailable) return aUnavailable ? -1 : 1;\n          return a.key.compareTo(b.key);\n        });\n    }\n    final result = indexed.map((entry) => entry.value).toList(growable: false);\n    _visibleTrackCacheSource = source;\n    _visibleTrackCacheQuery = query;\n    _visibleTrackCacheSort = _trackSort;\n    _visibleTrackCache = result;\n    return result;\n  }\n\n  List<Map<String, dynamic>> get _visiblePlaylists {''',
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "              onChanged: (_) => setState(() {}),",
    "              onChanged: _scheduleTrackSearch,\n              onSubmitted: _submitTrackSearch,",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "if (value != null) setState(() => _trackSort = value);",
    "if (value != null) {\n                        setState(() {\n                          _trackSort = value;\n                          _invalidateVisibleTracks();\n                        });\n                      }",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "key: const Key('track-list'),\n                            itemCount: visible.length,",
    "key: const Key('track-list'),\n                            itemExtent: 72,\n                            itemCount: visible.length,",
)
# Two image classes have stable fit lines; bound remote decode dimensions separately.
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "artwork,\n                            fit: BoxFit.cover,",
    "artwork,\n                            fit: BoxFit.cover,\n                            cacheWidth: 512,\n                            cacheHeight: 512,",
)
replace(
    "ui/musicark_ui/lib/yandex_workspace.dart",
    "artwork,\n                          fit: BoxFit.cover,",
    "artwork,\n                          fit: BoxFit.cover,\n                          cacheWidth: 96,\n                          cacheHeight: 96,",
)

# Version bump.
replace("pyproject.toml", 'version = "0.13.0"', 'version = "0.14.0"')
replace("src/musicark/__init__.py", '__version__ = "0.13.0"', '__version__ = "0.14.0"')
replace("ui/musicark_ui/pubspec.yaml", "version: 0.13.0+1", "version: 0.14.0+1")
replace("ui/musicark_ui/lib/app_info.dart", "0.13.0", "0.14.0")

print("v0.14 targeted patch applied")
