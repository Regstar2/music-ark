#!/usr/bin/env python3
"""Apply targeted v0.11.1 UI/bridge edits in a checked-out worktree.

This helper is temporary development machinery for the self-hosted runner.  It
uses exact replacements so a changed base fails closed instead of silently
rewriting an unexpected file.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {path}: {old[:100]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path}, found {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_local_library() -> None:
    path = "ui/musicark_ui/lib/local_library_page.dart"
    replace_once(
        path,
        "import 'yandex_upload_bridge.dart';\nimport 'yandex_upload_dialog.dart';\n\nenum _TrackMenuAction { uploadYandex, details, reveal }",
        "import 'v0111_localizations_ext.dart';\nimport 'yandex_batch_upload_bridge.dart';\nimport 'yandex_batch_upload_dialog.dart';\nimport 'yandex_upload_bridge.dart';\nimport 'yandex_upload_dialog.dart';\n\nenum _TrackMenuAction { details, reveal }",
    )
    replace_once(
        path,
        """    ContentLabelBridgeClient? contentLabelBridge,
    YandexUploadBridgeClient? yandexUploadBridge,
  }) : folderPicker = folderPicker ?? const SystemLocalFolderPicker(),
       metadataBridge = metadataBridge ??
           (bridge is MusicArkBridge ? const MetadataBridge() : null),
       contentLabelBridge = contentLabelBridge ??
           (bridge is MusicArkBridge ? const ContentLabelBridge() : null),
       yandexUploadBridge = yandexUploadBridge ??
           (bridge is MusicArkBridge ? const YandexUploadBridge() : null);

  final MusicArkBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final LocalFileActions fileActions;
  final MetadataBridgeClient? metadataBridge;
  final ContentLabelBridgeClient? contentLabelBridge;
  final YandexUploadBridgeClient? yandexUploadBridge;
""",
        """    ContentLabelBridgeClient? contentLabelBridge,
    YandexUploadBridgeClient? yandexUploadBridge,
    YandexBatchUploadBridgeClient? yandexBatchUploadBridge,
  }) : folderPicker = folderPicker ?? const SystemLocalFolderPicker(),
       metadataBridge = metadataBridge ??
           (bridge is MusicArkBridge ? const MetadataBridge() : null),
       contentLabelBridge = contentLabelBridge ??
           (bridge is MusicArkBridge ? const ContentLabelBridge() : null),
       yandexUploadBridge = yandexUploadBridge ??
           (bridge is MusicArkBridge ? const YandexUploadBridge() : null),
       yandexBatchUploadBridge = yandexBatchUploadBridge ??
           (bridge is MusicArkBridge ? const YandexBatchUploadBridge() : null);

  final MusicArkBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final LocalFileActions fileActions;
  final MetadataBridgeClient? metadataBridge;
  final ContentLabelBridgeClient? contentLabelBridge;
  final YandexUploadBridgeClient? yandexUploadBridge;
  final YandexBatchUploadBridgeClient? yandexBatchUploadBridge;
""",
    )
    replace_once(
        path,
        """  Set<int> _selectedRootIds = <int>{};
  bool _selectionInitialized = false;
""",
        """  Set<int> _selectedRootIds = <int>{};
  Set<int> _selectedTrackIds = <int>{};
  bool _selectionInitialized = false;
""",
    )
    replace_once(
        path,
        """        _selectionInitialized = true;
        _tracks = tracks;
        _total = int.tryParse('${tracksPayload['count'] ?? 0}') ?? 0;
""",
        """        _selectionInitialized = true;
        _tracks = tracks;
        final visibleIds = tracks
            .map((item) => int.tryParse('${item['id']}'))
            .whereType<int>()
            .toSet();
        _selectedTrackIds = _selectedTrackIds.where(visibleIds.contains).toSet();
        _total = int.tryParse('${tracksPayload['count'] ?? 0}') ?? 0;
""",
    )
    replace_once(
        path,
        """  Future<void> _uploadToYandex(Map<String, dynamic> track) async {
    final bridge = widget.yandexUploadBridge;
    if (bridge == null) return;
    final result = await showYandexUploadDialog(
      context: context,
      track: track,
      bridge: bridge,
    );
    if (!mounted || result == null) return;
    if (result.status == YandexUploadStatus.verified) {
      setState(() {
        _status = context.l10n.yandexUploadSuccess;
        _statusIsError = false;
      });
    }
  }
""",
        """  Future<void> _uploadToYandex(Map<String, dynamic> track) async {
    final bridge = widget.yandexUploadBridge;
    if (bridge == null) return;
    String? preferredKind;
    final batchBridge = widget.yandexBatchUploadBridge;
    if (batchBridge != null) {
      try {
        final managed = await batchBridge.managedPlaylists();
        for (final raw in (managed['roles'] as List? ?? const [])) {
          if (raw is! Map) continue;
          final role = Map<String, dynamic>.from(raw);
          if (role['role'] == 'uploaded' && role['configured'] == true) {
            preferredKind = '${role['playlistKind'] ?? ''}'.trim();
            if (preferredKind!.isEmpty) preferredKind = null;
            break;
          }
        }
      } catch (_) {
        preferredKind = null;
      }
    }
    if (!mounted) return;
    final result = await showYandexUploadDialog(
      context: context,
      track: track,
      bridge: bridge,
      preferredPlaylistKind: preferredKind,
    );
    if (!mounted || result == null) return;
    if (result.status == YandexUploadStatus.verified) {
      setState(() {
        _status = context.l10n.yandexUploadSuccess;
        _statusIsError = false;
      });
    }
  }

  void _toggleTrackSelection(Map<String, dynamic> track, bool selected) {
    final id = int.tryParse('${track['id']}');
    if (id == null) return;
    setState(() {
      if (selected) {
        _selectedTrackIds.add(id);
      } else {
        _selectedTrackIds.remove(id);
      }
    });
  }

  void _selectAllVisibleTracks() {
    setState(() {
      _selectedTrackIds.addAll(
        _tracks.map((track) => int.tryParse('${track['id']}')).whereType<int>(),
      );
    });
  }

  void _clearTrackSelection() => setState(() => _selectedTrackIds.clear());

  List<Map<String, dynamic>> _selectedTracks() => _tracks
      .where((track) => _selectedTrackIds.contains(int.tryParse('${track['id']}')))
      .toList(growable: false);

  Future<void> _bulkUploadToYandex() async {
    final uploadBridge = widget.yandexUploadBridge;
    final batchBridge = widget.yandexBatchUploadBridge;
    final selected = _selectedTracks();
    if (uploadBridge == null || batchBridge == null || selected.isEmpty) return;
    final allRoots = _allSelected();
    final localContext = allRoots
        ? context.l10n.v0111AllFolders
        : _selectedRootIds.length == 1
        ? _singleSelectedRootPath()
        : _folderFilterLabel();
    final result = await showYandexBatchUploadDialog(
      context: context,
      tracks: selected,
      targetBridge: uploadBridge,
      batchBridge: batchBridge,
      localContext: localContext,
      localContextTooltip: _selectedRootIds.length == 1 ? _singleSelectedRootPath() : null,
    );
    if (!mounted || result == null) return;
    setState(() {
      _status = context.l10n.v0111BatchFinished;
      _statusIsError = false;
      _selectedTrackIds.clear();
    });
  }
""",
    )
    replace_once(
        path,
        """                  _buildToolbar(l10n),
                  if (_status != null || _error != null) ...[
""",
        """                  _buildToolbar(l10n),
                  if (_selectedTrackIds.isNotEmpty) ...[
                    const SizedBox(height: AppUiTokens.compactGap),
                    _buildBulkToolbar(),
                  ],
                  if (_status != null || _error != null) ...[
""",
    )
    replace_once(
        path,
        """  Widget _buildMessageLine() {
""",
        """  Widget _buildBulkToolbar() {
    final l10n = context.l10n;
    final visibleIds = _tracks
        .map((track) => int.tryParse('${track['id']}'))
        .whereType<int>()
        .toSet();
    final allVisibleSelected = visibleIds.isNotEmpty && visibleIds.every(_selectedTrackIds.contains);
    return Card(
      key: const Key('local-bulk-toolbar'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              l10n.v0111Selected(_selectedTrackIds.length),
              key: const Key('local-selection-count'),
              style: Theme.of(context).textTheme.titleSmall,
            ),
            if (!allVisibleSelected)
              OutlinedButton(
                key: const Key('local-select-all-visible'),
                onPressed: _selectAllVisibleTracks,
                child: Text(l10n.v0111SelectAllVisible),
              ),
            FilledButton.icon(
              key: const Key('local-bulk-upload-yandex'),
              onPressed: widget.yandexUploadBridge != null && widget.yandexBatchUploadBridge != null
                  ? _bulkUploadToYandex
                  : null,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: Text(l10n.v0111UploadToYandex),
            ),
            TextButton(
              key: const Key('local-clear-selection'),
              onPressed: _clearTrackSelection,
              child: Text(l10n.v0111ClearSelection),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageLine() {
""",
    )
    replace_once(
        path,
        """        children: [
          Expanded(flex: 5, child: Text(l10n.localColumnTrack, style: style)),
""",
        """        children: [
          const SizedBox(width: 48),
          Expanded(flex: 5, child: Text(l10n.localColumnTrack, style: style)),
""",
    )
    replace_once(
        path,
        """          const SizedBox(width: 132),
""",
        """          const SizedBox(width: 176),
""",
    )
    replace_once(
        path,
        """            children: [
              const SizedBox(width: 12),
              Expanded(
""",
        """            children: [
              const SizedBox(width: 6),
              SizedBox(
                width: 42,
                child: Checkbox(
                  key: Key('local-select-${track['id']}'),
                  value: _selectedTrackIds.contains(int.tryParse('${track['id']}')),
                  onChanged: (value) => _toggleTrackSelection(track, value == true),
                ),
              ),
              Expanded(
""",
    )
    replace_once(
        path,
        """              SizedBox(width: 132, child: _buildTrackActions(track, l10n)),
""",
        """              SizedBox(width: 176, child: _buildTrackActions(track, l10n)),
""",
    )
    replace_once(
        path,
        """          child: Row(
            children: [
              _LocalArtwork(
""",
        """          child: Row(
            children: [
              Checkbox(
                key: Key('local-select-${track['id']}'),
                value: _selectedTrackIds.contains(int.tryParse('${track['id']}')),
                onChanged: (value) => _toggleTrackSelection(track, value == true),
              ),
              const SizedBox(width: 4),
              _LocalArtwork(
""",
    )
    replace_once(
        path,
        """        if (widget.metadataBridge != null)
          IconButton(
            key: Key('local-edit-${track['id']}'),
            tooltip: l10n.localEditMetadata,
            onPressed: () => _edit(track),
            icon: const Icon(Icons.edit_outlined),
          ),
        PopupMenuButton<_TrackMenuAction>(
""",
        """        if (widget.metadataBridge != null)
          IconButton(
            key: Key('local-edit-${track['id']}'),
            tooltip: l10n.localEditMetadata,
            onPressed: () => _edit(track),
            icon: const Icon(Icons.edit_outlined),
          ),
        if (widget.yandexUploadBridge != null)
          IconButton(
            key: Key('local-upload-yandex-${track['id']}'),
            tooltip: context.l10n.v0111UploadToYandex,
            onPressed: () => _uploadToYandex(track),
            icon: const Icon(Icons.cloud_upload_outlined),
          ),
        PopupMenuButton<_TrackMenuAction>(
""",
    )
    replace_once(
        path,
        """            switch (action) {
              case _TrackMenuAction.uploadYandex:
                _uploadToYandex(track);
                break;
              case _TrackMenuAction.details:
""",
        """            switch (action) {
              case _TrackMenuAction.details:
""",
    )
    replace_once(
        path,
        """          itemBuilder: (context) => [
            if (widget.yandexUploadBridge != null)
              PopupMenuItem(
                key: Key('local-upload-yandex-${track['id']}'),
                value: _TrackMenuAction.uploadYandex,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.cloud_upload_outlined),
                  title: Text(l10n.yandexUploadMenuAction),
                ),
              ),
            PopupMenuItem(
""",
        """          itemBuilder: (context) => [
            PopupMenuItem(
""",
    )


def patch_single_dialog() -> None:
    path = "ui/musicark_ui/lib/yandex_upload_dialog.dart"
    replace_once(
        path,
        """  required Map<String, dynamic> track,
  required YandexUploadBridgeClient bridge,
}) => showDialog<YandexUploadResult>(
  context: context,
  barrierDismissible: false,
  builder: (_) => YandexUploadDialog(track: track, bridge: bridge),
);
""",
        """  required Map<String, dynamic> track,
  required YandexUploadBridgeClient bridge,
  String? preferredPlaylistKind,
}) => showDialog<YandexUploadResult>(
  context: context,
  barrierDismissible: false,
  builder: (_) => YandexUploadDialog(
    track: track,
    bridge: bridge,
    preferredPlaylistKind: preferredPlaylistKind,
  ),
);
""",
    )
    replace_once(
        path,
        """    required this.track,
    required this.bridge,
  });

  final Map<String, dynamic> track;
  final YandexUploadBridgeClient bridge;
""",
        """    required this.track,
    required this.bridge,
    this.preferredPlaylistKind,
  });

  final Map<String, dynamic> track;
  final YandexUploadBridgeClient bridge;
  final String? preferredPlaylistKind;
""",
    )
    replace_once(
        path,
        """        _authenticated = targets.authenticated;
        _playlists = targets.playlists;
        _loadingTargets = false;
""",
        """        _authenticated = targets.authenticated;
        _playlists = targets.playlists;
        final preferred = widget.preferredPlaylistKind?.trim();
        if (preferred != null &&
            preferred.isNotEmpty &&
            targets.playlists.any((item) => item.playlistKind == preferred)) {
          _selectedPlaylistKind = preferred;
        }
        _loadingTargets = false;
""",
    )


def patch_sync_bridge() -> None:
    path = "ui/musicark_ui/lib/sync_bridge.dart"
    replace_once(
        path,
        """  Future<Map<String, dynamic>> history({int limit = 20});
  Future<Map<String, dynamic>> apply(String planId, {required bool confirm});
  Future<Map<String, dynamic>> cancel(String planId);
  Future<Map<String, dynamic>> setAction(String externalId, String action);
""",
        """  Future<Map<String, dynamic>> history({int limit = 20});
  Future<Map<String, dynamic>> apply(
    String planId, {
    required bool confirm,
    bool rightsConfirmed = false,
  });
  Future<Map<String, dynamic>> cancel(String planId);
  Future<Map<String, dynamic>> setAction(String externalId, String action);
  Future<Map<String, dynamic>> recoveryTracks({String filter = 'all', int limit = 500, int offset = 0});
""",
    )
    replace_once(
        path,
        """  Future<Map<String, dynamic>> apply(String planId, {required bool confirm}) =>
      _run('apply', planId: planId, confirm: confirm);
""",
        """  Future<Map<String, dynamic>> apply(
    String planId, {
    required bool confirm,
    bool rightsConfirmed = false,
  }) => _run(
    'apply',
    planId: planId,
    confirm: confirm,
    rightsConfirmed: rightsConfirmed,
  );
""",
    )
    replace_once(
        path,
        """  @override
  Future<Map<String, dynamic>> setAction(String externalId, String action) =>
      _run('set_action', externalId: externalId, action: action);

  Future<Map<String, dynamic>> _run(
""",
        """  @override
  Future<Map<String, dynamic>> setAction(String externalId, String action) =>
      _run('set_action', externalId: externalId, action: action);

  @override
  Future<Map<String, dynamic>> recoveryTracks({
    String filter = 'all',
    int limit = 500,
    int offset = 0,
  }) => _run('recovery_tracks', filter: filter, limit: limit, offset: offset);

  Future<Map<String, dynamic>> _run(
""",
    )
    replace_once(
        path,
        """    int? limit,
    bool confirm = false,
  }) async {
""",
        """    int? limit,
    int? offset,
    String? filter,
    bool confirm = false,
    bool rightsConfirmed = false,
  }) async {
""",
    )
    replace_once(
        path,
        """      if (limit != null) ...['--limit', '$limit'],
      if (confirm) '--confirm',
""",
        """      if (limit != null) ...['--limit', '$limit'],
      if (offset != null) ...['--offset', '$offset'],
      if (filter != null && filter.isNotEmpty) ...['--filter', filter],
      if (confirm) '--confirm',
      if (rightsConfirmed) '--rights-confirmed',
""",
    )
    replace_once(
        path,
        """  Future<Map<String, dynamic>> apply(String planId, {required bool confirm}) async {
    if (!confirm) throw const SyncBridgeException('confirmation_required', 'confirm required');
    applyCalls++;
""",
        """  Future<Map<String, dynamic>> apply(
    String planId, {
    required bool confirm,
    bool rightsConfirmed = false,
  }) async {
    if (!confirm) throw const SyncBridgeException('confirmation_required', 'confirm required');
    applyCalls++;
""",
    )
    replace_once(
        path,
        """  @override
  Future<Map<String, dynamic>> setAction(String externalId, String action) async {
""",
        """  @override
  Future<Map<String, dynamic>> recoveryTracks({
    String filter = 'all',
    int limit = 500,
    int offset = 0,
  }) async {
    final items = <Map<String, dynamic>>[
      {
        'externalId': 'unavailable-1',
        'title': 'Unavailable Track',
        'artists': ['Artist'],
        'album': 'Album',
        'collections': [
          {'playlistKind': 'focus', 'title': 'Focus'},
        ],
        'providerAvailability': 'unavailable',
        'localFileId': 77,
        'localFileName': 'Unavailable Track.mp3',
        'localExtension': '.mp3',
        'recoveryState': 'unavailable_local_available',
        'localMp3Ready': true,
      },
    ];
    return {
      'summary': {
        'unavailableTracks': 1,
        'unavailableRecoverable': 1,
        'unavailableMissingLocal': 0,
        'censoredTracks': 0,
        'censoredRecoverable': 0,
        'censoredNeedsReview': 0,
        'needsReview': 0,
      },
      'count': items.length,
      'items': items,
    };
  }

  @override
  Future<Map<String, dynamic>> setAction(String externalId, String action) async {
""",
    )
    replace_once(
        path,
        """        'plannerVersion': 1,
""",
        """        'plannerVersion': 2,
""",
    )
    replace_once(
        path,
        """          'blockerCount': 5,
        },
""",
        """          'blockerCount': 5,
          'unavailableTracks': 1,
          'unavailableRecoverable': 1,
          'unavailableMissingLocal': 0,
          'censoredTracks': 0,
          'censoredRecoverable': 0,
          'censoredNeedsReview': 0,
          'readyToUpload': 0,
          'uploadBlocked': 0,
          'uploadByRole': {'censored': 0, 'unavailable': 0},
        },
""",
    )


def patch_sync_page() -> None:
    path = "ui/musicark_ui/lib/sync_page.dart"
    replace_once(
        path,
        """import 'sync_bridge.dart';
import 'sync_localizations_ext.dart';
""",
        """import 'scope_context_bar.dart';
import 'sync_bridge.dart';
import 'sync_localizations_ext.dart';
import 'v0111_localizations_ext.dart';
import 'yandex_batch_upload_bridge.dart';
""",
    )
    replace_once(
        path,
        """    this.onOpenDownloads,
    this.onOpenMatching,
  });

  final SyncBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final VoidCallback? onOpenDownloads;
  final VoidCallback? onOpenMatching;
""",
        """    this.onOpenDownloads,
    this.onOpenMatching,
    this.managedPlaylistBridge,
  });

  final SyncBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final VoidCallback? onOpenDownloads;
  final VoidCallback? onOpenMatching;
  final YandexBatchUploadBridgeClient? managedPlaylistBridge;
""",
    )
    replace_once(
        path,
        """  Map<String, dynamic>? _diff;
  String _scopeType = 'all';
  String? _scopeId;
  SyncPlanFilter? _planFilter;
""",
        """  Map<String, dynamic>? _diff;
  Map<String, dynamic> _managed = const {};
  List<Map<String, dynamic>> _recovery = const [];
  String _recoveryFilter = 'all';
  String _scopeType = 'all';
  String? _scopeId;
  SyncPlanFilter? _planFilter;

  YandexBatchUploadBridgeClient? get _managedBridge =>
      widget.managedPlaylistBridge ??
      (widget.bridge is SyncBridge ? const YandexBatchUploadBridge() : null);
""",
    )
    replace_once(
        path,
        """      if (_diff == null || _needsRefresh(_diff!)) {
        await _refreshDiff();
      }
""",
        """      await _refreshRecoveryManaged();
      if (_diff == null || _needsRefresh(_diff!)) {
        await _refreshDiff();
      }
""",
    )
    replace_once(
        path,
        """  bool _currentCanBeShown(
""",
        """  Future<void> _refreshRecoveryManaged() async {
    try {
      final recovery = await widget.bridge.recoveryTracks(
        filter: _recoveryFilter,
        limit: 500,
      );
      Map<String, dynamic> managed = const {};
      final bridge = _managedBridge;
      if (bridge != null) managed = await bridge.managedPlaylists();
      if (!mounted) return;
      setState(() {
        _recovery = _maps(recovery['items']);
        _managed = managed;
      });
    } catch (_) {
      // Recovery/managed presentation must not hide the existing Sync plan.
    }
  }

  bool _currentCanBeShown(
""",
    )
    replace_once(
        path,
        """  Future<void> _synchronize() async {
    if (_busy) return;
    if (_target['targetConfigured'] != true) {
      setState(() => _error = context.l10n.syncSelectFolderFirst);
      return;
    }

    Map<String, dynamic>? fresh;
""",
        """  Future<void> _synchronize() async {
    if (_busy) return;

    Map<String, dynamic>? fresh;
""",
    )
    replace_once(
        path,
        """    final downloads = _int(summary['readyToDownload']);
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);
    final l10n = context.l10n;

    if (downloads == 0) {
""",
        """    final downloads = _int(summary['readyToDownload']);
    final uploads = _int(summary['readyToUpload']);
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);
    final l10n = context.l10n;

    if (downloads > 0 && _target['targetConfigured'] != true) {
      setState(() => _error = l10n.syncSelectFolderFirst);
      return;
    }

    if (downloads == 0 && uploads == 0) {
""",
    )
    replace_once(
        path,
        """    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        final dialogL10n = dialogContext.l10n;
        return AlertDialog(
          key: const Key('sync-confirmation'),
          title: Text(dialogL10n.syncConfirmTitle),
          content: Text(
            '${dialogL10n.syncConfirmQueueCount(downloads)}\\n\\n'
            '${dialogL10n.syncSafetyNote}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: Text(dialogL10n.cancel),
            ),
            FilledButton(
              key: const Key('sync-confirm'),
              onPressed: () => Navigator.pop(dialogContext, true),
              child: Text(dialogL10n.syncConfirmAction),
            ),
          ],
        );
      },
    );
    if (confirmed != true) return;

    Map<String, dynamic>? result;
    await _run(() async {
      result = await widget.bridge.apply('${fresh!['id']}', confirm: true);
""",
        """    var rightsConfirmed = uploads == 0;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          final dialogL10n = dialogContext.l10n;
          final byRole = summary['uploadByRole'] is Map
              ? Map<String, dynamic>.from(summary['uploadByRole'] as Map)
              : const <String, dynamic>{};
          final folder = _target['targetConfigured'] == true
              ? '${_target['targetPath'] ?? ''}'
              : dialogL10n.v0111FolderNotRequired;
          return AlertDialog(
            key: const Key('sync-confirmation'),
            title: Text(dialogL10n.syncConfirmTitle),
            content: SizedBox(
              width: 560,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(dialogL10n.v0111ConfirmDownloads(downloads)),
                  Text(dialogL10n.v0111ConfirmUploads(uploads)),
                  if (uploads > 0) ...[
                    const SizedBox(height: 8),
                    Text(dialogL10n.v0111ConfirmRole(dialogL10n.v0111RoleCensored, _int(byRole['censored']))),
                    Text(dialogL10n.v0111ConfirmRole(dialogL10n.v0111RoleUnavailable, _int(byRole['unavailable']))),
                  ],
                  const SizedBox(height: 12),
                  Text('${dialogL10n.v0111LocalFolder}: $folder'),
                  if (uploads > 0)
                    CheckboxListTile(
                      key: const Key('sync-upload-rights'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      value: rightsConfirmed,
                      onChanged: (value) => setDialogState(() => rightsConfirmed = value == true),
                      title: Text(dialogL10n.v0111SyncRights),
                    ),
                  const SizedBox(height: 8),
                  Text(dialogL10n.syncSafetyNote),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: Text(dialogL10n.cancel),
              ),
              FilledButton(
                key: const Key('sync-confirm'),
                onPressed: rightsConfirmed ? () => Navigator.pop(dialogContext, true) : null,
                child: Text(dialogL10n.syncConfirmAction),
              ),
            ],
          );
        },
      ),
    );
    if (confirmed != true) return;

    Map<String, dynamic>? result;
    await _run(() async {
      result = await widget.bridge.apply(
        '${fresh!['id']}',
        confirm: true,
        rightsConfirmed: rightsConfirmed,
      );
""",
    )
    replace_once(
        path,
        """      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
    if (!mounted || result == null) return;
""",
        """      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
    await _refreshRecoveryManaged();
    if (!mounted || result == null) return;
""",
    )
    replace_once(
        path,
        """                  _buildToolbar(l10n),
                  if (_status != null || _error != null) ...[
""" if False else "___never___",
        "___never___",
    )

    # Persistent scope context directly below the existing controls.
    replace_once(
        path,
        """              _controls(),
              if (_error != null) ...[
""",
        """              _controls(),
              const SizedBox(height: AppUiTokens.compactGap),
              _scopeContextBar(),
              if (_error != null) ...[
""",
    )
    replace_once(
        path,
        """                _summaryCard(_diff!),
                const SizedBox(height: AppUiTokens.sectionGap),
                _details(_diff!),
              ],
""",
        """                _summaryCard(_diff!),
                const SizedBox(height: AppUiTokens.sectionGap),
                _details(_diff!),
                const SizedBox(height: AppUiTokens.sectionGap),
                _managedPlaylistCard(),
                const SizedBox(height: AppUiTokens.sectionGap),
                _recoveryCard(),
              ],
""",
    )
    replace_once(
        path,
        """    final ready = _int(summary['readyToDownload']);
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);
    final configured = _target['targetConfigured'] == true;
""",
        """    final ready = _int(summary['readyToDownload']);
    final readyUpload = _int(summary['readyToUpload']);
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);
    final configured = _target['targetConfigured'] == true;
    final canApply = !_busy && (ready == 0 || configured) && (ready + readyUpload > 0);
""",
    )
    replace_once(
        path,
        """                      onPressed: !_busy && configured ? _synchronize : null,
                      icon: const Icon(Icons.sync),
                      label: Text(l10n.syncSynchronizeTracks(ready)),
""",
        """                      onPressed: canApply ? _synchronize : null,
                      icon: const Icon(Icons.sync),
                      label: Text(l10n.syncSynchronizeTracks(ready + readyUpload)),
""",
    )
    replace_once(
        path,
        """      _MetricData(
        keyName: 'attention',
        label: l10n.syncMetricAttention,
        value: _blockerCount(summary),
        icon: Icons.help_outline,
        attention: _blockerCount(summary) > 0,
      ),
""",
        """      _MetricData(
        keyName: 'unavailable',
        label: l10n.v0111UnavailableTracks,
        value: _int(summary['unavailableTracks']),
        icon: Icons.cloud_off_outlined,
        attention: _int(summary['unavailableTracks']) > 0,
      ),
      _MetricData(
        keyName: 'censored',
        label: l10n.v0111CensoredTracks,
        value: _int(summary['censoredTracks']),
        icon: Icons.explicit_outlined,
        attention: _int(summary['censoredNeedsReview']) > 0,
      ),
      _MetricData(
        keyName: 'upload',
        label: l10n.v0111ReadyToUpload,
        value: _int(summary['readyToUpload']),
        icon: Icons.cloud_upload_outlined,
        emphasized: _int(summary['readyToUpload']) > 0,
      ),
      _MetricData(
        keyName: 'attention',
        label: l10n.syncMetricAttention,
        value: _blockerCount(summary),
        icon: Icons.help_outline,
        attention: _blockerCount(summary) > 0,
      ),
""",
    )
    replace_once(
        path,
        """    final keyPrefix = switch (type) {
      'enqueue_download' => 'sync-download',
""",
        """    final keyPrefix = switch (type) {
      'upload_local_to_yandex' => 'sync-upload',
      'enqueue_download' => 'sync-download',
""",
    )
    replace_once(
        path,
        """    switch (type) {
      case 'enqueue_download':
""",
        """    switch (type) {
      case 'upload_local_to_yandex':
        final role = '${metadata['targetRole'] ?? ''}';
        return _OperationPresentation(
          actionLabel: l10n.v0111UploadToYandexGroup,
          reason: role == 'censored' ? l10n.v0111RoleCensored : l10n.v0111RoleUnavailable,
          statusLabel: l10n.syncStatusReady,
          icon: Icons.cloud_upload_outlined,
        );
      case 'enqueue_download':
""",
    )
    replace_once(
        path,
        """  SyncPlanFilter _defaultFilter(_OperationBuckets buckets) {
""",
        """  Widget _scopeContextBar() {
    final summary = _diff == null ? const <String, dynamic>{} : _summary(_diff!);
    final readyDownloads = _int(summary['readyToDownload']);
    final readyUploads = _int(summary['readyToUpload']);
    final configured = _target['targetConfigured'] == true;
    final folder = configured
        ? '${_target['targetPath'] ?? ''}'
        : readyDownloads == 0 && readyUploads > 0
        ? context.l10n.v0111FolderNotRequired
        : context.l10n.v0111FolderNotSelected;
    return ScopeContextBar(
      collection: _selectedScopeTitle(),
      localFolders: folder,
      localFoldersTooltip: configured ? '${_target['targetPath'] ?? ''}' : null,
      localNotRequired: !configured && readyDownloads == 0 && readyUploads > 0,
    );
  }

  String? _managedKind(String role) {
    for (final raw in (_managed['roles'] as List? ?? const [])) {
      if (raw is! Map) continue;
      final item = Map<String, dynamic>.from(raw);
      if (item['role'] == role && item['configured'] == true) {
        final kind = '${item['playlistKind'] ?? ''}'.trim();
        if (kind.isNotEmpty) return kind;
      }
    }
    return null;
  }

  Future<void> _setManagedPlaylist(String role, String playlistKind) async {
    final bridge = _managedBridge;
    if (bridge == null) return;
    await _run(() async {
      _managed = await bridge.setManagedPlaylist(role: role, playlistKind: playlistKind);
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
  }

  Future<void> _ensureManagedPlaylists() async {
    final bridge = _managedBridge;
    if (bridge == null) return;
    var confirmCreate = false;
    if (_managed['canCreatePlaylists'] == true) {
      confirmCreate = await showDialog<bool>(
            context: context,
            builder: (dialogContext) => AlertDialog(
              title: Text(dialogContext.l10n.v0111ManagedPlaylists),
              content: Text(dialogContext.l10n.v0111ManagedCreateUnavailable),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: Text(dialogContext.l10n.cancel),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, true),
                  child: Text(dialogContext.l10n.v0111Ensure),
                ),
              ],
            ),
          ) ??
          false;
      if (!confirmCreate) return;
    }
    await _run(() async {
      _managed = await bridge.ensureManagedPlaylists(confirmCreate: confirmCreate);
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
  }

  Widget _managedPlaylistCard() {
    final l10n = context.l10n;
    final roles = _maps(_managed['roles']);
    final playlists = _maps(_managed['availablePlaylists']);
    if (_managedBridge == null) return const SizedBox.shrink();
    String roleTitle(String role, String fallback) => switch (role) {
      'censored' => l10n.v0111RoleCensored,
      'uploaded' => l10n.v0111RoleUploaded,
      'unavailable' => l10n.v0111RoleUnavailable,
      _ => fallback,
    };
    return Card(
      key: const Key('sync-managed-playlists'),
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(l10n.v0111ManagedPlaylists, style: Theme.of(context).textTheme.titleMedium),
                ),
                OutlinedButton(
                  key: const Key('sync-managed-ensure'),
                  onPressed: _busy ? null : _ensureManagedPlaylists,
                  child: Text(l10n.v0111Ensure),
                ),
              ],
            ),
            if (_managed['canCreatePlaylists'] != true) ...[
              const SizedBox(height: 6),
              Text(l10n.v0111ManagedCreateUnavailable, style: Theme.of(context).textTheme.bodySmall),
            ],
            const SizedBox(height: 10),
            for (final role in roles) ...[
              LayoutBuilder(
                builder: (context, constraints) {
                  final roleName = '${role['role'] ?? ''}';
                  final current = role['configured'] == true ? '${role['playlistKind'] ?? ''}' : null;
                  final title = roleTitle(roleName, '${role['defaultTitle'] ?? roleName}');
                  final selector = DropdownButtonFormField<String>(
                    key: Key('sync-managed-$roleName'),
                    initialValue: playlists.any((item) => '${item['playlistKind']}' == current) ? current : null,
                    isExpanded: true,
                    decoration: InputDecoration(
                      labelText: role['configured'] == true ? l10n.v0111ManagedConfigured : l10n.v0111ManagedNotConfigured,
                      isDense: true,
                    ),
                    items: playlists
                        .map(
                          (item) => DropdownMenuItem<String>(
                            value: '${item['playlistKind']}',
                            child: Text('${item['title'] ?? ''}', overflow: TextOverflow.ellipsis),
                          ),
                        )
                        .toList(growable: false),
                    onChanged: _busy ? null : (value) {
                      if (value != null) _setManagedPlaylist(roleName, value);
                    },
                  );
                  if (constraints.maxWidth < 620) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [Text(title), const SizedBox(height: 4), selector],
                    );
                  }
                  return Row(
                    children: [
                      SizedBox(width: 190, child: Text(title)),
                      const SizedBox(width: 12),
                      Expanded(child: selector),
                    ],
                  );
                },
              ),
              const SizedBox(height: 8),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _changeRecoveryFilter(String filter) async {
    setState(() => _recoveryFilter = filter);
    try {
      final payload = await widget.bridge.recoveryTracks(filter: filter, limit: 500);
      if (!mounted) return;
      setState(() => _recovery = _maps(payload['items']));
    } catch (error) {
      if (mounted) setState(() => _error = _message(error));
    }
  }

  Future<void> _restoreTrack(Map<String, dynamic> item) async {
    final bridge = _managedBridge;
    final localId = int.tryParse('${item['localFileId'] ?? ''}');
    final state = '${item['recoveryState'] ?? ''}';
    final role = state.startsWith('censored_') ? 'censored' : 'unavailable';
    final kind = _managedKind(role);
    if (bridge == null || localId == null || kind == null) return;
    var rights = false;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: Text(dialogContext.l10n.v0111ReadyToRestore),
          content: CheckboxListTile(
            key: const Key('sync-recovery-rights'),
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: rights,
            onChanged: (value) => setDialogState(() => rights = value == true),
            title: Text(dialogContext.l10n.v0111SyncRights),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: Text(dialogContext.l10n.cancel),
            ),
            FilledButton(
              onPressed: rights ? () => Navigator.pop(dialogContext, true) : null,
              child: Text(dialogContext.l10n.v0111UploadToYandex),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true) return;
    await _run(() async {
      await bridge.uploadBatch(
        localFileIds: [localId],
        playlistKind: kind,
        confirm: true,
        rightsConfirmed: true,
        batchId: 'recovery-${DateTime.now().microsecondsSinceEpoch}-$localId',
      );
    });
    await _refreshRecoveryManaged();
    await _refreshDiff();
  }

  Widget _recoveryCard() {
    final l10n = context.l10n;
    String filterLabel(String value) => switch (value) {
      'recoverable' => l10n.v0111RecoveryRecoverable,
      'missing_local' => l10n.v0111RecoveryMissingLocal,
      'needs_review' => l10n.v0111RecoveryNeedsReview,
      _ => l10n.v0111RecoveryAll,
    };
    return Card(
      key: const Key('sync-recovery-section'),
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l10n.v0111UnavailableSection, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final value in const ['all', 'recoverable', 'missing_local', 'needs_review'])
                  ChoiceChip(
                    key: Key('sync-recovery-filter-$value'),
                    selected: _recoveryFilter == value,
                    label: Text(filterLabel(value)),
                    onSelected: (_) => _changeRecoveryFilter(value),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            if (_recovery.isEmpty)
              Text(l10n.syncNoOperations)
            else
              for (final item in _recovery.take(100))
                ListTile(
                  key: Key('sync-recovery-${item['externalId']}'),
                  leading: const Icon(Icons.cloud_off_outlined),
                  title: Text('${item['artists'] is List ? (item['artists'] as List).join(', ') : ''} — ${item['title'] ?? ''}'),
                  subtitle: Text(
                    '${item['providerAvailability'] == 'unavailable' ? l10n.v0111YandexUnavailable : l10n.v0111YandexUnknown} · '
                    '${item['localFileId'] != null ? l10n.v0111LocalFound : l10n.v0111LocalMissing}',
                  ),
                  trailing: item['localMp3Ready'] == true && _managedKind(
                            '${item['recoveryState']}'.startsWith('censored_') ? 'censored' : 'unavailable',
                          ) !=
                          null
                      ? OutlinedButton(
                          key: Key('sync-recovery-restore-${item['externalId']}'),
                          onPressed: _busy ? null : () => _restoreTrack(item),
                          child: Text(l10n.v0111ReadyToRestore),
                        )
                      : null,
                ),
          ],
        ),
      ),
    );
  }

  SyncPlanFilter _defaultFilter(_OperationBuckets buckets) {
""",
    )
    replace_once(
        path,
        """  static int _blockerCount(Map<String, dynamic> summary) =>
      _int(summary['missingUndecided']) +
      _int(summary['identityReview']) +
      _int(summary['notAnalyzed']) +
      _int(summary['variantIssues']);
""",
        """  static int _blockerCount(Map<String, dynamic> summary) =>
      _int(summary['missingUndecided']) +
      _int(summary['identityReview']) +
      _int(summary['notAnalyzed']) +
      _int(summary['variantIssues']) +
      _int(summary['uploadBlocked']) +
      _int(summary['censoredNeedsReview']);
""",
    )


def patch_upload_local_test() -> None:
    path = "ui/musicark_ui/test/yandex_upload_local_library_test.dart"
    replace_once(
        path,
        """    await tester.tap(find.byKey(const Key('local-track-menu-77')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('local-upload-yandex-77')), findsOneWidget);
    expect(find.text('Загрузить в Яндекс Музыку'), findsOneWidget);

    await tester.tap(find.byKey(const Key('local-upload-yandex-77')));
""",
        """    expect(find.byKey(const Key('local-upload-yandex-77')), findsOneWidget);
    expect(
      tester.widget<IconButton>(find.byKey(const Key('local-upload-yandex-77'))).tooltip,
      'Загрузить в Яндекс Музыку',
    );
    await tester.tap(find.byKey(const Key('local-track-menu-77')));
    await tester.pumpAndSettle();
    expect(find.text('Загрузить в Яндекс Музыку'), findsNothing);
    await tester.tapAt(const Offset(40, 40));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('local-upload-yandex-77')));
""",
    )


def main() -> None:
    patch_local_library()
    patch_single_dialog()
    patch_sync_bridge()
    patch_sync_page()
    patch_upload_local_test()


if __name__ == "__main__":
    main()
