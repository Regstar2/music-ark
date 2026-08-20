from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8", newline="\n")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# 1. Production wiring for bulk upload.
# ---------------------------------------------------------------------------
replace_once(
    "ui/musicark_ui/lib/app_shell.dart",
    "    this.yandexUploadBridge,\n  });",
    "    this.yandexUploadBridge,\n    this.yandexBatchUploadBridge,\n  });",
)
replace_once(
    "ui/musicark_ui/lib/app_shell.dart",
    "  final YandexUploadBridgeClient? yandexUploadBridge;\n",
    "  final YandexUploadBridgeClient? yandexUploadBridge;\n  final YandexBatchUploadBridgeClient? yandexBatchUploadBridge;\n",
)
replace_once(
    "ui/musicark_ui/lib/app_shell.dart",
    "                              yandexUploadBridge: widget.yandexUploadBridge,\n                            )",
    "                              yandexUploadBridge: widget.yandexUploadBridge,\n                              yandexBatchUploadBridge: widget.yandexBatchUploadBridge,\n                            )",
)
replace_once(
    "ui/musicark_ui/lib/app_shell.dart",
    "                              managedPlaylistBridge: const YandexBatchUploadBridge(),\n",
    "                              managedPlaylistBridge: widget.yandexBatchUploadBridge,\n",
)

replace_once(
    "ui/musicark_ui/lib/main.dart",
    "import 'yandex_upload_bridge.dart';\n",
    "import 'yandex_batch_upload_bridge.dart';\nimport 'yandex_upload_bridge.dart';\n",
)
replace_once(
    "ui/musicark_ui/lib/main.dart",
    "    this.yandexUploadBridge,\n    this.settingsStorage,",
    "    this.yandexUploadBridge,\n    this.yandexBatchUploadBridge,\n    this.settingsStorage,",
)
replace_once(
    "ui/musicark_ui/lib/main.dart",
    "  final YandexUploadBridgeClient? yandexUploadBridge;\n  final AppSettingsStorage? settingsStorage;",
    "  final YandexUploadBridgeClient? yandexUploadBridge;\n  final YandexBatchUploadBridgeClient? yandexBatchUploadBridge;\n  final AppSettingsStorage? settingsStorage;",
)
replace_once(
    "ui/musicark_ui/lib/main.dart",
    "    final featureYandexUpload = widget.yandexUploadBridge ??\n        (injectedMode ? null : const YandexUploadBridge());\n",
    "    final featureYandexUpload = widget.yandexUploadBridge ??\n        (injectedMode ? null : const YandexUploadBridge());\n    final featureYandexBatchUpload = widget.yandexBatchUploadBridge ??\n        (injectedMode ? null : const YandexBatchUploadBridge());\n",
)
replace_once(
    "ui/musicark_ui/lib/main.dart",
    "            yandexUploadBridge: featureYandexUpload,\n            settings: _settings,",
    "            yandexUploadBridge: featureYandexUpload,\n            yandexBatchUploadBridge: featureYandexBatchUpload,\n            settings: _settings,",
)

# Fix the known narrow-width sort overflow exposed by the self-hosted runner.
replace_once(
    "ui/musicark_ui/lib/local_library_page.dart",
    "                  child: DropdownButtonFormField<String>(\n                    key: const Key('local-sort'),\n                    initialValue: _sort,",
    "                  child: DropdownButtonFormField<String>(\n                    key: const Key('local-sort'),\n                    initialValue: _sort,\n                    isExpanded: true,",
)
for getter in ("localSortArtist", "localSortTitle", "localSortAlbum", "localSortDuration", "localSortPath"):
    replace_once(
        "ui/musicark_ui/lib/local_library_page.dart",
        f"child: Text(l10n.{getter}),",
        f"child: Text(l10n.{getter}, maxLines: 1, overflow: TextOverflow.ellipsis),",
    )

# ---------------------------------------------------------------------------
# 2. Recovery payload: server-side playlist filter + stable filter metadata.
# ---------------------------------------------------------------------------
replace_once(
    "src/musicark/recovery/service.py",
    "    def payload(\n        self,\n        *,\n        filter_name: str = \"all\",\n        limit: int = 500,\n        offset: int = 0,\n    ) -> dict[str, Any]:",
    "    def payload(\n        self,\n        *,\n        filter_name: str = \"all\",\n        playlist_kind: str | None = None,\n        limit: int = 500,\n        offset: int = 0,\n    ) -> dict[str, Any]:",
)
replace_once(
    "src/musicark/recovery/service.py",
    "        safe_limit = max(1, min(int(limit), 1000))\n        safe_offset = max(0, int(offset))\n        return {\n            \"summary\": self._summary_for(all_items),\n            \"count\": len(items),\n            \"items\": [item.to_dict() for item in items[safe_offset : safe_offset + safe_limit]],\n        }",
    "        playlist_map: dict[str, str] = {}\n        for item in all_items:\n            for collection in item.collections:\n                kind = str(collection.get(\"playlistKind\") or \"\").strip()\n                if not kind:\n                    continue\n                title = str(collection.get(\"title\") or kind).strip() or kind\n                playlist_map.setdefault(kind, title)\n\n        selected_playlist_kind = str(playlist_kind or \"\").strip()\n        if selected_playlist_kind:\n            items = [\n                item\n                for item in items\n                if any(\n                    str(collection.get(\"playlistKind\") or \"\").strip() == selected_playlist_kind\n                    for collection in item.collections\n                )\n            ]\n\n        safe_limit = max(1, min(int(limit), 1000))\n        safe_offset = max(0, int(offset))\n        return {\n            \"summary\": self._summary_for(all_items),\n            \"count\": len(items),\n            \"playlists\": [\n                {\"playlistKind\": kind, \"title\": playlist_map[kind]}\n                for kind in sorted(playlist_map, key=lambda value: (playlist_map[value].casefold(), value))\n            ],\n            \"selectedPlaylistKind\": selected_playlist_kind or None,\n            \"items\": [item.to_dict() for item in items[safe_offset : safe_offset + safe_limit]],\n        }",
)

replace_once(
    "src/musicark/sync/service.py",
    "    def recovery(self, *, filter_name: str = \"all\", limit: int = 500, offset: int = 0) -> dict[str, Any]:\n        return self._recovery.payload(filter_name=filter_name, limit=limit, offset=offset)",
    "    def recovery(\n        self,\n        *,\n        filter_name: str = \"all\",\n        playlist_kind: str | None = None,\n        limit: int = 500,\n        offset: int = 0,\n    ) -> dict[str, Any]:\n        return self._recovery.payload(\n            filter_name=filter_name,\n            playlist_kind=playlist_kind,\n            limit=limit,\n            offset=offset,\n        )",
)

replace_once(
    "src/musicark/sync/bridge.py",
    "    parser.add_argument(\"--filter\", default=\"all\")\n",
    "    parser.add_argument(\"--filter\", default=\"all\")\n    parser.add_argument(\"--playlist-kind\", default=None)\n",
)
replace_once(
    "src/musicark/sync/bridge.py",
    "            filter_name=args.filter,\n            limit=max(1, min(args.limit, 1000)),",
    "            filter_name=args.filter,\n            playlist_kind=args.playlist_kind,\n            limit=max(1, min(args.limit, 1000)),",
)

# ---------------------------------------------------------------------------
# 3. Flutter sync bridge supports the playlist filter end-to-end.
# ---------------------------------------------------------------------------
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "  Future<Map<String, dynamic>> recoveryTracks({\n    String filter = 'all',\n    int limit = 500,\n    int offset = 0,\n  });",
    "  Future<Map<String, dynamic>> recoveryTracks({\n    String filter = 'all',\n    String? playlistKind,\n    int limit = 500,\n    int offset = 0,\n  });",
)
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "  Future<Map<String, dynamic>> recoveryTracks({\n    String filter = 'all',\n    int limit = 500,\n    int offset = 0,\n  }) => _run(\n    'recovery_tracks',\n    filter: filter,\n    limit: limit,\n    offset: offset,\n  );",
    "  Future<Map<String, dynamic>> recoveryTracks({\n    String filter = 'all',\n    String? playlistKind,\n    int limit = 500,\n    int offset = 0,\n  }) => _run(\n    'recovery_tracks',\n    filter: filter,\n    playlistKind: playlistKind,\n    limit: limit,\n    offset: offset,\n  );",
)
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "    String? filter,\n    int? limit,",
    "    String? filter,\n    String? playlistKind,\n    int? limit,",
)
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "      if (filter != null && filter.isNotEmpty) ...['--filter', filter],\n      if (limit != null)",
    "      if (filter != null && filter.isNotEmpty) ...['--filter', filter],\n      if (playlistKind != null && playlistKind.isNotEmpty) ...[\n        '--playlist-kind',\n        playlistKind,\n      ],\n      if (limit != null)",
)
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "  Future<Map<String, dynamic>> recoveryTracks({\n    String filter = 'all',\n    int limit = 500,\n    int offset = 0,\n  }) async {",
    "  Future<Map<String, dynamic>> recoveryTracks({\n    String filter = 'all',\n    String? playlistKind,\n    int limit = 500,\n    int offset = 0,\n  }) async {",
)
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "    return {\n      'summary': {\n        'unavailableTracks': 1,",
    "    final filtered = playlistKind == null || playlistKind.isEmpty\n        ? items\n        : items.where((item) {\n            final collections = item['collections'] as List? ?? const [];\n            return collections.whereType<Map>().any(\n              (entry) => '${entry['playlistKind'] ?? ''}' == playlistKind,\n            );\n          }).toList(growable: false);\n    return {\n      'summary': {\n        'unavailableTracks': 1,",
)
replace_once(
    "ui/musicark_ui/lib/sync_bridge.dart",
    "      'count': items.length,\n      'items': items,\n    };",
    "      'count': filtered.length,\n      'playlists': const [\n        {'playlistKind': 'focus', 'title': 'Focus'},\n      ],\n      'selectedPlaylistKind': playlistKind,\n      'items': filtered,\n    };",
)

# ---------------------------------------------------------------------------
# 4. Sync UX: two workspaces instead of two long lists stacked vertically.
# ---------------------------------------------------------------------------
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "enum SyncPlanFilter { all, download, decision, matching, variant, localOnly }\n",
    "enum SyncPlanFilter { all, download, decision, matching, variant, localOnly }\n\nenum _SyncWorkspaceTab { plan, recovery }\n",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "  String _recoveryFilter = 'all';\n",
    "  String _recoveryFilter = 'all';\n  String _recoveryPlaylistKind = '';\n  _SyncWorkspaceTab _workspaceTab = _SyncWorkspaceTab.plan;\n",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "    final recovery = await widget.bridge.recoveryTracks(\n      filter: _recoveryFilter,\n    );",
    "    final recovery = await widget.bridge.recoveryTracks(\n      filter: _recoveryFilter,\n      playlistKind: _recoveryPlaylistKind.isEmpty ? null : _recoveryPlaylistKind,\n    );",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "      final data = await widget.bridge.recoveryTracks(filter: filter);\n",
    "      final data = await widget.bridge.recoveryTracks(\n        filter: filter,\n        playlistKind: _recoveryPlaylistKind.isEmpty ? null : _recoveryPlaylistKind,\n      );\n",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "  String? _managedRoleKind(String role) {",
    "  Future<void> _changeRecoveryPlaylist(String value) async {\n    if (_busy) return;\n    final next = value == 'all' ? '' : value;\n    if (next == _recoveryPlaylistKind) return;\n    setState(() => _recoveryPlaylistKind = next);\n    await _run(() async {\n      final data = await widget.bridge.recoveryTracks(\n        filter: _recoveryFilter,\n        playlistKind: next.isEmpty ? null : next,\n      );\n      if (mounted) setState(() => _recovery = Map<String, dynamic>.from(data));\n    });\n  }\n\n  String? _managedRoleKind(String role) {",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "  Widget _recoverySection() {\n    final items = _maps(_recovery['items']);\n    return Card(",
    "  Widget _recoverySection() {\n    final items = _maps(_recovery['items']);\n    final playlists = _maps(_recovery['playlists']);\n    final playlistValue = _recoveryPlaylistKind.isEmpty ? 'all' : _recoveryPlaylistKind;\n    return Card(",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "            const SizedBox(height: 10),\n            if (items.isEmpty)",
    "            const SizedBox(height: 10),\n            SizedBox(\n              width: 360,\n              child: DropdownButtonFormField<String>(\n                key: const Key('sync-recovery-playlist-filter'),\n                initialValue: playlistValue,\n                isExpanded: true,\n                decoration: InputDecoration(\n                  labelText: context.l10n.v0111PlaylistFilter,\n                  prefixIcon: const Icon(Icons.queue_music_outlined),\n                  isDense: true,\n                ),\n                items: [\n                  DropdownMenuItem(\n                    value: 'all',\n                    child: Text(context.l10n.v0111AllPlaylists),\n                  ),\n                  for (final playlist in playlists)\n                    DropdownMenuItem(\n                      value: '${playlist['playlistKind']}',\n                      child: Text(\n                        '${playlist['title'] ?? playlist['playlistKind']}',\n                        maxLines: 1,\n                        overflow: TextOverflow.ellipsis,\n                      ),\n                    ),\n                ],\n                onChanged: _busy\n                    ? null\n                    : (value) {\n                        if (value != null) _changeRecoveryPlaylist(value);\n                      },\n              ),\n            ),\n            const SizedBox(height: 10),\n            if (items.isEmpty)",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "  Future<void> _run(Future<void> Function() action) async {",
    "  Widget _workspace(Map<String, dynamic> diff) {\n    final summary = _summary(diff);\n    final operationCount = _int(summary['operationCount']);\n    final recoveryCount = _int(_recovery['count']);\n    return Column(\n      crossAxisAlignment: CrossAxisAlignment.stretch,\n      children: [\n        Card(\n          key: const Key('sync-workspace-tabs'),\n          child: Padding(\n            padding: const EdgeInsets.all(8),\n            child: SegmentedButton<_SyncWorkspaceTab>(\n              segments: [\n                ButtonSegment(\n                  value: _SyncWorkspaceTab.plan,\n                  icon: const Icon(Icons.sync_alt_outlined),\n                  label: Text('${context.l10n.v0111SyncPlanTab} ($operationCount)'),\n                ),\n                ButtonSegment(\n                  value: _SyncWorkspaceTab.recovery,\n                  icon: const Icon(Icons.restore_outlined),\n                  label: Text('${context.l10n.v0111RecoveryTab} ($recoveryCount)'),\n                ),\n              ],\n              selected: {_workspaceTab},\n              onSelectionChanged: _busy\n                  ? null\n                  : (selection) => setState(() => _workspaceTab = selection.first),\n            ),\n          ),\n        ),\n        const SizedBox(height: AppUiTokens.sectionGap),\n        if (_workspaceTab == _SyncWorkspaceTab.plan)\n          _details(diff)\n        else ...[\n          _managedPlaylistsCard(),\n          const SizedBox(height: AppUiTokens.sectionGap),\n          _recoverySection(),\n        ],\n      ],\n    );\n  }\n\n  Future<void> _run(Future<void> Function() action) async {",
)
replace_once(
    "ui/musicark_ui/lib/sync_page.dart",
    "                _managedPlaylistsCard(),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _recoverySection(),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _details(_diff!),",
    "                _workspace(_diff!),",
)

replace_once(
    "ui/musicark_ui/lib/v0111_localizations_ext.dart",
    "  String get v0111UnavailableSection => _ru ? 'Недоступные в Яндекс Музыке' : 'Unavailable in Yandex Music';\n",
    "  String get v0111SyncPlanTab => _ru ? 'План синхронизации' : 'Sync plan';\n  String get v0111RecoveryTab => _ru ? 'Восстановление' : 'Recovery';\n  String get v0111PlaylistFilter => _ru ? 'Плейлист' : 'Playlist';\n  String get v0111AllPlaylists => _ru ? 'Все плейлисты' : 'All playlists';\n\n  String get v0111UnavailableSection => _ru ? 'Недоступные в Яндекс Музыке' : 'Unavailable in Yandex Music';\n",
)

# ---------------------------------------------------------------------------
# 5. Regression tests for server-side playlist filter and Flutter 3.44 teardown.
# ---------------------------------------------------------------------------
replace_once(
    "tests/test_v0111_recovery_upload.py",
    "    def test_disappearance_alone_becomes_review_not_unavailable(self) -> None:\n",
    "    def test_recovery_payload_filters_by_source_playlist(self) -> None:\n        self._insert_playlist_track(\"playlist-track-1\", availability=\"unavailable\", playlist_id=\"playlist:1\")\n        self._insert_playlist_track(\"playlist-track-2\", availability=\"unavailable\", playlist_id=\"playlist:2\")\n\n        payload = RecoveryService(self.db).payload(playlist_kind=\"1\")\n\n        self.assertEqual(payload[\"count\"], 1)\n        self.assertEqual(payload[\"items\"][0][\"externalId\"], \"playlist-track-1\")\n        self.assertEqual(\n            {item[\"playlistKind\"] for item in payload[\"playlists\"]},\n            {\"1\", \"2\"},\n        )\n        self.assertEqual(payload[\"selectedPlaylistKind\"], \"1\")\n\n    def test_disappearance_alone_becomes_review_not_unavailable(self) -> None:\n",
)

# Flutter 3.44 no longer permits setSurfaceSize(null) from global tearDown.
for test_path in (ROOT / "ui/musicark_ui/test").glob("*.dart"):
    text = test_path.read_text(encoding="utf-8")
    original = text
    text = re.sub(
        r"\n\s*tearDown\(\(\) async \{\s*await TestWidgetsFlutterBinding\.ensureInitialized\(\)\.setSurfaceSize\(null\);\s*\}\);\n",
        "\n",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"\n\s*tearDown\(\(\) => TestWidgetsFlutterBinding\.ensureInitialized\(\)\.setSurfaceSize\(null\)\);\n",
        "\n",
        text,
    )
    # Register cleanup while the widget test is active. Avoid duplicating if rerun.
    if "tester.binding.setSurfaceSize" in text and "addTearDown(() => tester.binding.setSurfaceSize(null));" not in text:
        text = re.sub(
            r"(\s+await tester\.binding\.setSurfaceSize\([^;]+;\n)",
            r"\1    addTearDown(() => tester.binding.setSurfaceSize(null));\n",
            text,
        )
    if text != original:
        test_path.write_text(text, encoding="utf-8", newline="\n")

# v0.11.1 sync tests now explicitly switch to the Recovery workspace.
path = "ui/musicark_ui/test/v0111_sync_page_test.dart"
text = read(path)
text = text.replace(
    "    expect(find.byKey(const Key('sync-recovery-section')), findsOneWidget);\n    expect(find.byKey(const Key('sync-managed-playlists')), findsOneWidget);\n    expect(find.byKey(const Key('sync-recovery-unavailable-1')), findsOneWidget);\n",
    "    expect(find.byKey(const Key('sync-workspace-tabs')), findsOneWidget);\n",
    1,
)
text = text.replace(
    "    await tester.ensureVisible(find.byKey(const Key('sync-recovery-section')));\n    await tester.pumpAndSettle();\n",
    "    await tester.tap(find.textContaining('Восстановление ('));\n    await tester.pumpAndSettle();\n    await tester.ensureVisible(find.byKey(const Key('sync-recovery-section')));\n    await tester.pumpAndSettle();\n",
    1,
)
text = text.replace(
    "    expect(find.byKey(const Key('sync-recovery-filter-needs_review')), findsOneWidget);\n    expect(find.byKey(const Key('sync-recovery-restore-unavailable-1')), findsOneWidget);\n",
    "    expect(find.byKey(const Key('sync-recovery-filter-needs_review')), findsOneWidget);\n    expect(find.byKey(const Key('sync-recovery-playlist-filter')), findsOneWidget);\n    expect(find.byKey(const Key('sync-recovery-restore-unavailable-1')), findsOneWidget);\n",
    1,
)
write(path, text)

print("v0.11.1 manual feedback patch applied")
