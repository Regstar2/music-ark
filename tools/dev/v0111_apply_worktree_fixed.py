from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Update legacy schema assertions to the additive v0.11.1 schema.
# ---------------------------------------------------------------------------
for rel in [
    "tests/test_database.py",
    "tests/test_local_library_v04.py",
    "tests/test_migrations_v03.py",
    "tests/test_migrations_v05.py",
    "tests/test_migrations_v06.py",
    "tests/test_migrations_v08.py",
    "tests/test_migrations_v1.py",
    "tests/test_platform_bridge.py",
    "tests/test_variant_acceptance_v082.py",
    "tests/test_variant_v051.py",
]:
    text = read(rel)
    text = text.replace('"1.8.4"', '"1.9.0"')
    text = text.replace("'1.8.4'", "'1.9.0'")
    write(rel, text)

# Database smoke test should assert the new additive tables too.
rel = "tests/test_database.py"
text = read(rel)
anchor = '            self.assertIn("variant_user_acceptance", tables)\n'
addition = anchor + '''            self.assertIn("managed_yandex_playlists", tables)\n            self.assertIn("yandex_upload_mappings", tables)\n            self.assertIn("provider_track_availability_history", tables)\n            self.assertIn("yandex_upload_batches", tables)\n            self.assertIn("yandex_upload_batch_items", tables)\n'''
if 'self.assertIn("managed_yandex_playlists", tables)' not in text:
    text = replace_once(text, anchor, addition, label="database table assertions")
write(rel, text)

# v0.10 experimental entry point stays blocked, but production capability was
# deliberately enabled by v0.11.0 and must not be regressed by stale tests.
rel = "tests/test_yandex_experimental_upload.py"
text = read(rel)
old = '''    def test_production_upload_capabilities_remain_disabled(self) -> None:\n        capabilities = YandexMusicProvider().capabilities\n        self.assertFalse(capabilities.can_upload_tracks)\n        self.assertFalse(capabilities.supports_user_uploads)\n'''
new = '''    def test_production_upload_capabilities_are_separate_from_obsolete_probe(self) -> None:\n        capabilities = YandexMusicProvider().capabilities\n        self.assertTrue(capabilities.can_upload_tracks)\n        self.assertTrue(capabilities.supports_user_uploads)\n'''
if old in text:
    text = replace_once(text, old, new, label="experimental capability regression")
write(rel, text)

# v0.11.0 sync regression creates planner input directly. The new recovery
# inputs are empty in that regression, which preserves its original meaning.
rel = "tests/test_yandex_upload_production_service.py"
text = read(rel)
old = '''            local_fingerprint="local",\n            active_downloads={},\n        )\n'''
new = '''            recovery={},\n            managed={},\n            local_fingerprint="local",\n            active_downloads={},\n        )\n'''
if new not in text:
    text = replace_once(text, old, new, label="v0.11.0 planner input compatibility")
write(rel, text)

# ---------------------------------------------------------------------------
# Finish the Sync UI integration. Backend/bridges and focused tests already
# exist on the branch; this connects them to the production page.
# ---------------------------------------------------------------------------
rel = "ui/musicark_ui/lib/sync_page.dart"
text = read(rel)

if "scope_context_bar.dart" not in text:
    text = replace_once(
        text,
        "import 'folder_picker.dart';\nimport 'sync_bridge.dart';\nimport 'sync_localizations_ext.dart';\n",
        "import 'folder_picker.dart';\nimport 'scope_context_bar.dart';\nimport 'sync_bridge.dart';\nimport 'sync_localizations_ext.dart';\nimport 'v0111_localizations_ext.dart';\nimport 'yandex_batch_upload_bridge.dart';\n",
        label="sync imports",
    )

old = '''    this.onOpenDownloads,\n    this.onOpenMatching,\n  });\n\n  final SyncBridgeClient bridge;\n  final LocalFolderPicker folderPicker;\n  final VoidCallback? onOpenDownloads;\n  final VoidCallback? onOpenMatching;\n'''
new = '''    this.onOpenDownloads,\n    this.onOpenMatching,\n    this.managedPlaylistBridge,\n  });\n\n  final SyncBridgeClient bridge;\n  final LocalFolderPicker folderPicker;\n  final VoidCallback? onOpenDownloads;\n  final VoidCallback? onOpenMatching;\n  final YandexBatchUploadBridgeClient? managedPlaylistBridge;\n'''
if "final YandexBatchUploadBridgeClient? managedPlaylistBridge;" not in text:
    text = replace_once(text, old, new, label="sync constructor")

old = '''  String _scopeType = 'all';\n  String? _scopeId;\n  SyncPlanFilter? _planFilter;\n'''
new = '''  String _scopeType = 'all';\n  String? _scopeId;\n  SyncPlanFilter? _planFilter;\n  Map<String, dynamic> _recovery = const {};\n  Map<String, dynamic> _managed = const {};\n  String _recoveryFilter = 'all';\n'''
if "Map<String, dynamic> _recovery" not in text:
    text = replace_once(text, old, new, label="sync state")

# Load recovery and managed playlist state together with the existing context.
old = '''      final results = await Future.wait([\n        widget.bridge.scopes(),\n        widget.bridge.target(),\n        widget.bridge.current(),\n      ]);\n'''
new = '''      final results = await Future.wait([\n        widget.bridge.scopes(),\n        widget.bridge.target(),\n        widget.bridge.current(),\n        widget.bridge.recoveryTracks(),\n        widget.managedPlaylistBridge?.managedPlaylists() ??\n            Future<Map<String, dynamic>>.value(const {}),\n      ]);\n'''
if "widget.bridge.recoveryTracks()," not in text:
    text = replace_once(text, old, new, label="sync load futures")

old = '''      final rawCurrent = results[2]['plan'];\n      final current =\n          rawCurrent is Map ? Map<String, dynamic>.from(rawCurrent) : null;\n'''
new = '''      final rawCurrent = results[2]['plan'];\n      final current =\n          rawCurrent is Map ? Map<String, dynamic>.from(rawCurrent) : null;\n      final recovery = Map<String, dynamic>.from(results[3]);\n      final managed = Map<String, dynamic>.from(results[4]);\n'''
if "final recovery = Map<String, dynamic>.from(results[3]);" not in text:
    text = replace_once(text, old, new, label="sync loaded maps")

old = '''        _scopeId = scopeId;\n        _diff = _currentCanBeShown(current, scopeType, scopeId) ? current : null;\n        _loading = false;\n'''
new = '''        _scopeId = scopeId;\n        _diff = _currentCanBeShown(current, scopeType, scopeId) ? current : null;\n        _recovery = recovery;\n        _managed = managed;\n        _loading = false;\n'''
if "_recovery = recovery;" not in text:
    text = replace_once(text, old, new, label="sync state assignment")

# Replace the old download-only confirmation/apply path with a mixed plan path.
start = text.index("  Future<void> _synchronize() async {")
end = text.index("  Future<void> _run(Future<void> Function() action) async {", start)
new_sync = r'''  Future<void> _synchronize() async {
    if (_busy) return;

    Map<String, dynamic>? fresh;
    await _run(() async {
      fresh = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
      _diff = fresh;
    });
    if (!mounted || fresh == null) return;

    final summary = _summary(fresh!);
    final downloads = _int(summary['readyToDownload']);
    final uploads = _int(summary['readyToUpload']);
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);
    final l10n = context.l10n;

    if (downloads > 0 && _target['targetConfigured'] != true) {
      setState(() => _error = l10n.syncSelectFolderFirst);
      return;
    }

    if (downloads == 0 && uploads == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            queued > 0
                ? l10n.syncNothingNewQueued
                : blockers > 0
                    ? l10n.syncNothingNewAttention
                    : l10n.syncNothingNewComplete,
          ),
        ),
      );
      return;
    }

    var rightsConfirmed = uploads == 0;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          final dialogL10n = dialogContext.l10n;
          final uploadByRole = summary['uploadByRole'] is Map
              ? Map<String, dynamic>.from(summary['uploadByRole'] as Map)
              : const <String, dynamic>{};
          return AlertDialog(
            key: const Key('sync-confirmation'),
            title: Text(dialogL10n.syncConfirmTitle),
            content: SizedBox(
              width: 520,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(dialogL10n.v0111ConfirmDownloads(downloads)),
                  const SizedBox(height: 6),
                  Text(dialogL10n.v0111ConfirmUploads(uploads)),
                  if (uploads > 0) ...[
                    const SizedBox(height: 12),
                    Text(
                      dialogL10n.v0111ConfirmRole(
                        dialogL10n.v0111RoleCensored,
                        _int(uploadByRole['censored']),
                      ),
                    ),
                    Text(
                      dialogL10n.v0111ConfirmRole(
                        dialogL10n.v0111RoleUnavailable,
                        _int(uploadByRole['unavailable']),
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  ScopeContextBar(
                    collection: _selectedScopeTitle(),
                    localFolders: _syncLocalContext(summary),
                    localFoldersTooltip: _target['targetConfigured'] == true
                        ? '${_target['targetPath'] ?? ''}'
                        : null,
                    localNotRequired:
                        downloads == 0 && _target['targetConfigured'] != true,
                  ),
                  if (uploads > 0) ...[
                    const SizedBox(height: 12),
                    CheckboxListTile(
                      key: const Key('sync-upload-rights'),
                      contentPadding: EdgeInsets.zero,
                      value: rightsConfirmed,
                      onChanged: (value) => setDialogState(
                        () => rightsConfirmed = value == true,
                      ),
                      title: Text(dialogL10n.v0111SyncRights),
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                  ],
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
                onPressed: uploads == 0 || rightsConfirmed
                    ? () => Navigator.pop(dialogContext, true)
                    : null,
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
        rightsConfirmed: uploads > 0 && rightsConfirmed,
      );
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
      await _reloadRecoveryAndManaged();
    });
    if (!mounted || result == null) return;

    final rawResult = result!['result'];
    final data = rawResult is Map
        ? Map<String, dynamic>.from(rawResult)
        : const <String, dynamic>{};
    final downloadResult = data['downloads'] is Map
        ? Map<String, dynamic>.from(data['downloads'] as Map)
        : data;
    final uploadResult = data['uploads'] is Map
        ? Map<String, dynamic>.from(data['uploads'] as Map)
        : const <String, dynamic>{};
    final uploadDone = _int(uploadResult['verified']) +
        _int(uploadResult['processing']) +
        _int(uploadResult['deliveryUnknown']);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '${context.l10n.syncApplyResult(
            _int(downloadResult['enqueued']),
            _int(downloadResult['skipped']),
            _int(downloadResult['failed']),
          )}${uploads > 0 ? ' · ${context.l10n.v0111UploadToYandexGroup}: $uploadDone/$uploads' : ''}',
        ),
        action: widget.onOpenDownloads == null || downloads == 0
            ? null
            : SnackBarAction(
                label: context.l10n.navDownloads,
                onPressed: widget.onOpenDownloads!,
              ),
      ),
    );
  }

  Future<void> _reloadRecoveryAndManaged() async {
    final recovery = await widget.bridge.recoveryTracks(filter: _recoveryFilter);
    final managed = widget.managedPlaylistBridge == null
        ? const <String, dynamic>{}
        : await widget.managedPlaylistBridge!.managedPlaylists();
    if (!mounted) return;
    setState(() {
      _recovery = Map<String, dynamic>.from(recovery);
      _managed = Map<String, dynamic>.from(managed);
    });
  }

  String _syncLocalContext(Map<String, dynamic> summary) {
    if (_target['targetConfigured'] == true) {
      return '${_target['targetPath'] ?? ''}';
    }
    return _int(summary['readyToDownload']) == 0
        ? context.l10n.v0111FolderNotRequired
        : context.l10n.v0111FolderNotSelected;
  }

  Future<void> _changeRecoveryFilter(String filter) async {
    if (_busy || filter == _recoveryFilter) return;
    setState(() => _recoveryFilter = filter);
    await _run(() async {
      final data = await widget.bridge.recoveryTracks(filter: filter);
      if (mounted) setState(() => _recovery = Map<String, dynamic>.from(data));
    });
  }

  String? _managedRoleKind(String role) {
    for (final raw in _maps(_managed['roles'])) {
      if ('${raw['role']}' == role && raw['configured'] == true) {
        final value = '${raw['playlistKind'] ?? ''}'.trim();
        if (value.isNotEmpty) return value;
      }
    }
    return null;
  }

  Future<void> _ensureManagedPlaylists() async {
    final bridge = widget.managedPlaylistBridge;
    if (bridge == null) return;
    await _run(() async {
      _managed = await bridge.ensureManagedPlaylists(confirmCreate: false);
    });
  }

  Future<void> _setManagedPlaylist(String role, String playlistKind) async {
    final bridge = widget.managedPlaylistBridge;
    if (bridge == null || playlistKind.trim().isEmpty) return;
    await _run(() async {
      _managed = await bridge.setManagedPlaylist(
        role: role,
        playlistKind: playlistKind,
      );
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
  }

  Future<void> _restoreRecoveryTrack(Map<String, dynamic> item) async {
    final bridge = widget.managedPlaylistBridge;
    final localFileId = int.tryParse('${item['localFileId']}');
    final state = '${item['recoveryState'] ?? ''}';
    final role = state.startsWith('censored_') ? 'censored' : 'unavailable';
    final playlistKind = _managedRoleKind(role);
    if (bridge == null || localFileId == null || playlistKind == null) return;

    var rights = false;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: Text(dialogContext.l10n.v0111ReadyToRestore),
          content: CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: rights,
            onChanged: (value) => setDialogState(() => rights = value == true),
            title: Text(dialogContext.l10n.v0111SyncRights),
            controlAffinity: ListTileControlAffinity.leading,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: Text(dialogContext.l10n.cancel),
            ),
            FilledButton(
              onPressed: rights ? () => Navigator.pop(dialogContext, true) : null,
              child: Text(dialogContext.l10n.v0111ReadyToRestore),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true) return;
    await _run(() async {
      await bridge.uploadBatch(
        localFileIds: [localFileId],
        playlistKind: playlistKind,
        confirm: true,
        rightsConfirmed: true,
        batchId: 'recovery-${DateTime.now().microsecondsSinceEpoch}',
      );
      await _reloadRecoveryAndManaged();
    });
  }

  Widget _scopeContext() {
    final summary = _diff == null ? const <String, dynamic>{} : _summary(_diff!);
    final configured = _target['targetConfigured'] == true;
    final localContext = configured
        ? '${_target['targetPath'] ?? ''}'
        : _int(summary['readyToDownload']) == 0
            ? context.l10n.v0111FolderNotRequired
            : context.l10n.v0111FolderNotSelected;
    return ScopeContextBar(
      collection: _selectedScopeTitle(),
      localFolders: localContext,
      localFoldersTooltip: configured ? '${_target['targetPath'] ?? ''}' : null,
      localNotRequired: !configured && _int(summary['readyToDownload']) == 0,
    );
  }

  Widget _v0111Summary(Map<String, dynamic> diff) {
    final summary = _summary(diff);
    final entries = <(String, int)>[
      (context.l10n.v0111UnavailableTracks, _int(summary['unavailableTracks'])),
      (context.l10n.v0111CensoredTracks, _int(summary['censoredTracks'])),
      (context.l10n.v0111Recoverable, _int(summary['unavailableRecoverable']) + _int(summary['censoredRecoverable'])),
      (context.l10n.v0111ReadyToUpload, _int(summary['readyToUpload'])),
    ];
    return Card(
      key: const Key('sync-recovery-summary'),
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: Wrap(
          spacing: AppUiTokens.sectionGap,
          runSpacing: AppUiTokens.compactGap,
          children: [
            for (final entry in entries)
              SizedBox(
                width: 220,
                child: Row(
                  children: [
                    Expanded(child: Text(entry.$1)),
                    Text('${entry.$2}', style: Theme.of(context).textTheme.titleMedium),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _managedPlaylistsCard() {
    final bridge = widget.managedPlaylistBridge;
    if (bridge == null) return const SizedBox.shrink();
    final roles = _maps(_managed['roles']);
    final available = _maps(_managed['availablePlaylists']);
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
                  child: Text(
                    context.l10n.v0111ManagedPlaylists,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                OutlinedButton(
                  onPressed: _busy ? null : _ensureManagedPlaylists,
                  child: Text(context.l10n.v0111Ensure),
                ),
              ],
            ),
            if (_managed['canCreatePlaylists'] != true) ...[
              const SizedBox(height: 6),
              Text(
                context.l10n.v0111ManagedCreateUnavailable,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 8),
            for (final role in roles) ...[
              _managedRoleRow(role, available),
              const SizedBox(height: 6),
            ],
          ],
        ),
      ),
    );
  }

  Widget _managedRoleRow(
    Map<String, dynamic> role,
    List<Map<String, dynamic>> available,
  ) {
    final roleId = '${role['role'] ?? ''}';
    final configured = role['configured'] == true;
    final selected = configured ? '${role['playlistKind'] ?? ''}' : null;
    final title = '${role['defaultTitle'] ?? roleId}';
    return LayoutBuilder(
      builder: (context, constraints) => Wrap(
        spacing: 10,
        runSpacing: 6,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          SizedBox(
            width: 190,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.labelLarge),
                Text(
                  configured
                      ? context.l10n.v0111ManagedConfigured
                      : context.l10n.v0111ManagedNotConfigured,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          SizedBox(
            width: constraints.maxWidth < 560 ? constraints.maxWidth : 320,
            child: DropdownButtonFormField<String>(
              key: Key('sync-managed-$roleId'),
              initialValue: available.any(
                (item) => '${item['playlistKind'] ?? ''}' == selected,
              )
                  ? selected
                  : null,
              isExpanded: true,
              decoration: const InputDecoration(isDense: true),
              hint: Text(context.l10n.v0111Select),
              items: [
                for (final playlist in available)
                  DropdownMenuItem(
                    value: '${playlist['playlistKind']}',
                    child: Text(
                      '${playlist['title'] ?? playlist['playlistKind']}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value != null) _setManagedPlaylist(roleId, value);
                    },
            ),
          ),
        ],
      ),
    );
  }

  Widget _recoverySection() {
    final items = _maps(_recovery['items']);
    return Card(
      key: const Key('sync-recovery-section'),
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              context.l10n.v0111UnavailableSection,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _recoveryFilterChip('all', context.l10n.v0111RecoveryAll),
                _recoveryFilterChip('recoverable', context.l10n.v0111RecoveryRecoverable),
                _recoveryFilterChip('missing_local', context.l10n.v0111RecoveryMissingLocal),
                _recoveryFilterChip('needs_review', context.l10n.v0111RecoveryNeedsReview),
              ],
            ),
            const SizedBox(height: 10),
            if (items.isEmpty)
              Text(context.l10n.syncNoOperations)
            else
              for (final item in items) _recoveryRow(item),
          ],
        ),
      ),
    );
  }

  Widget _recoveryFilterChip(String value, String label) => ChoiceChip(
        key: Key('sync-recovery-filter-$value'),
        label: Text(label),
        selected: _recoveryFilter == value,
        onSelected: _busy ? null : (_) => _changeRecoveryFilter(value),
      );

  Widget _recoveryRow(Map<String, dynamic> item) {
    final externalId = '${item['externalId'] ?? ''}';
    final artists = (item['artists'] as List? ?? const []).join(', ');
    final collections = _maps(item['collections'])
        .map((entry) => '${entry['title'] ?? entry['playlistKind'] ?? ''}')
        .where((value) => value.isNotEmpty)
        .join(', ');
    final localReady = item['localMp3Ready'] == true;
    final needsReview = '${item['recoveryState'] ?? ''}'.contains('needs_review');
    final role = '${item['recoveryState'] ?? ''}'.startsWith('censored_')
        ? 'censored'
        : 'unavailable';
    final canRestore = localReady && !needsReview && _managedRoleKind(role) != null;
    return Container(
      key: Key('sync-recovery-$externalId'),
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.cloud_off_outlined),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$artists${artists.isNotEmpty ? ' — ' : ''}${item['title'] ?? externalId}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (collections.isNotEmpty)
                  Text('${context.l10n.v0111SourcePlaylists}: $collections'),
                Text(
                  item['providerAvailability'] == 'unavailable'
                      ? context.l10n.v0111YandexUnavailable
                      : context.l10n.v0111YandexUnknown,
                ),
                Text(
                  localReady
                      ? context.l10n.v0111LocalFound
                      : context.l10n.v0111LocalMissing,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            key: Key('sync-recovery-restore-$externalId'),
            onPressed: canRestore ? () => _restoreRecoveryTrack(item) : null,
            icon: const Icon(Icons.cloud_upload_outlined),
            label: Text(
              localReady
                  ? context.l10n.v0111ReadyToRestore
                  : context.l10n.v0111NeedsLocalFile,
            ),
          ),
        ],
      ),
    );
  }

'''
text = text[:start] + new_sync + text[end:]

# Place persistent context and recovery UI into the page.
old = '''              _controls(),\n              if (_error != null) ...[\n'''
new = '''              _controls(),\n              const SizedBox(height: AppUiTokens.compactGap),\n              _scopeContext(),\n              if (_error != null) ...[\n'''
if "_scopeContext()," not in text:
    text = replace_once(text, old, new, label="scope context placement")

old = '''                _summaryCard(_diff!),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _details(_diff!),\n'''
new = '''                _summaryCard(_diff!),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _v0111Summary(_diff!),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _managedPlaylistsCard(),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _recoverySection(),\n                const SizedBox(height: AppUiTokens.sectionGap),\n                _details(_diff!),\n'''
if "_v0111Summary(_diff!)," not in text:
    text = replace_once(text, old, new, label="recovery sections placement")

# Sync button must remain enabled for upload-only plans without a download target.
old = '''                    FilledButton.icon(\n                      key: const Key('sync-now'),\n                      onPressed: !_busy && configured ? _synchronize : null,\n                      icon: const Icon(Icons.sync),\n                      label: Text(l10n.syncSynchronizeTracks(ready)),\n                    ),\n'''
new = '''                    FilledButton.icon(\n                      key: const Key('sync-now'),\n                      onPressed: !_busy &&\n                              (configured ||\n                                  (ready == 0 &&\n                                      _int(summary['readyToUpload']) > 0))\n                          ? _synchronize\n                          : null,\n                      icon: const Icon(Icons.sync),\n                      label: Text(\n                        l10n.syncSynchronizeTracks(\n                          ready + _int(summary['readyToUpload']),\n                        ),\n                      ),\n                    ),\n'''
if "ready + _int(summary['readyToUpload'])" not in text:
    text = replace_once(text, old, new, label="upload-only sync button")

write(rel, text)

print("v0.11.1 guarded integration edits applied")
