import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'app_ui_tokens.dart';
import 'folder_picker.dart';
import 'scope_context_bar.dart';
import 'sync_bridge.dart';
import 'sync_localizations_ext.dart';
import 'v0111_localizations_ext.dart';
import 'yandex_batch_upload_bridge.dart';

enum SyncPlanFilter { all, download, decision, matching, variant, localOnly }

class SyncPage extends StatefulWidget {
  const SyncPage({
    super.key,
    required this.bridge,
    this.folderPicker = const SystemLocalFolderPicker(),
    this.onOpenDownloads,
    this.onOpenMatching,
    this.managedPlaylistBridge,
  });

  final SyncBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final VoidCallback? onOpenDownloads;
  final VoidCallback? onOpenMatching;
  final YandexBatchUploadBridgeClient? managedPlaylistBridge;

  @override
  State<SyncPage> createState() => _SyncPageState();
}

class _SyncPageState extends State<SyncPage> {
  bool _loading = true;
  bool _busy = false;
  String? _error;
  List<Map<String, dynamic>> _scopes = const [];
  Map<String, dynamic> _target = const {};
  Map<String, dynamic>? _diff;
  String _scopeType = 'all';
  String? _scopeId;
  SyncPlanFilter? _planFilter;
  Map<String, dynamic> _recovery = const {};
  Map<String, dynamic> _managed = const {};
  String _recoveryFilter = 'all';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final results = await Future.wait([
        widget.bridge.scopes(),
        widget.bridge.target(),
        widget.bridge.current(),
        widget.bridge.recoveryTracks(),
        widget.managedPlaylistBridge?.managedPlaylists() ??
            Future<Map<String, dynamic>>.value(const {}),
      ]);
      if (!mounted) return;

      final scopes = _maps(results[0]['items']);
      final target = Map<String, dynamic>.from(results[1]);
      final rawCurrent = results[2]['plan'];
      final current = rawCurrent is Map
          ? Map<String, dynamic>.from(rawCurrent)
          : null;
      final recovery = Map<String, dynamic>.from(results[3]);
      final managed = Map<String, dynamic>.from(results[4]);

      var scopeType = 'all';
      String? scopeId;
      if (current != null && current['legacy'] != true) {
        final candidateType = '${current['scopeType'] ?? 'all'}';
        final candidateId = _nullableString(current['scopeId']);
        if (_scopeExists(scopes, candidateType, candidateId)) {
          scopeType = candidateType;
          scopeId = candidateId;
        }
      }
      if (!_scopeExists(scopes, scopeType, scopeId) && scopes.isNotEmpty) {
        scopeType = '${scopes.first['type'] ?? 'all'}';
        scopeId = _nullableString(scopes.first['id']);
      }

      setState(() {
        _scopes = scopes;
        _target = target;
        _scopeType = scopeType;
        _scopeId = scopeId;
        _diff = _currentCanBeShown(current, scopeType, scopeId)
            ? current
            : null;
        _recovery = recovery;
        _managed = managed;
        _loading = false;
      });

      if (_diff == null || _needsRefresh(_diff!)) {
        await _refreshDiff();
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = _message(error);
      });
    }
  }

  bool _currentCanBeShown(
    Map<String, dynamic>? current,
    String scopeType,
    String? scopeId,
  ) {
    if (current == null || current['legacy'] == true) return false;
    return '${current['scopeType'] ?? ''}' == scopeType &&
        _nullableString(current['scopeId']) == scopeId;
  }

  bool _needsRefresh(Map<String, dynamic> diff) {
    final status = '${diff['status'] ?? ''}';
    return status != 'planned';
  }

  Future<void> _refreshDiff() async {
    await _run(() async {
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
  }

  Future<void> _chooseTarget() async {
    final path = await widget.folderPicker.pickDirectory();
    if (path == null || path.trim().isEmpty) return;
    await _run(() async {
      _target = await widget.bridge.setTarget(path);
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
  }

  Future<void> _changeScope(String value) async {
    final parts = value.split('|');
    final nextType = parts.first;
    final nextId = parts.length > 1 && parts[1].isNotEmpty ? parts[1] : null;
    if (nextType == _scopeType && nextId == _scopeId) return;
    setState(() {
      _scopeType = nextType;
      _scopeId = nextId;
      _diff = null;
      _planFilter = null;
    });
    await _refreshDiff();
  }

  Future<void> _setAction(String externalId, String action) async {
    await _run(() async {
      await widget.bridge.setAction(externalId, action);
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
  }

  Future<void> _synchronize() async {
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
                      onChanged: (value) =>
                          setDialogState(() => rightsConfirmed = value == true),
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
    final uploadDone =
        _int(uploadResult['verified']) +
        _int(uploadResult['processing']) +
        _int(uploadResult['deliveryUnknown']);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '${context.l10n.syncApplyResult(_int(downloadResult['enqueued']), _int(downloadResult['skipped']), _int(downloadResult['failed']))}${uploads > 0 ? ' · ${context.l10n.v0111UploadToYandexGroup}: $uploadDone/$uploads' : ''}',
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
    final recovery = await widget.bridge.recoveryTracks(
      filter: _recoveryFilter,
    );
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
              onPressed: rights
                  ? () => Navigator.pop(dialogContext, true)
                  : null,
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
    final summary = _diff == null
        ? const <String, dynamic>{}
        : _summary(_diff!);
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
      (
        context.l10n.v0111Recoverable,
        _int(summary['unavailableRecoverable']) +
            _int(summary['censoredRecoverable']),
      ),
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
                    Text(
                      '${entry.$2}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
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
              initialValue:
                  available.any(
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
                _recoveryFilterChip(
                  'recoverable',
                  context.l10n.v0111RecoveryRecoverable,
                ),
                _recoveryFilterChip(
                  'missing_local',
                  context.l10n.v0111RecoveryMissingLocal,
                ),
                _recoveryFilterChip(
                  'needs_review',
                  context.l10n.v0111RecoveryNeedsReview,
                ),
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
    final needsReview = '${item['recoveryState'] ?? ''}'.contains(
      'needs_review',
    );
    final role = '${item['recoveryState'] ?? ''}'.startsWith('censored_')
        ? 'censored'
        : 'unavailable';
    final canRestore =
        localReady && !needsReview && _managedRoleKind(role) != null;
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

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    if (mounted) {
      setState(() {
        _busy = true;
        _error = null;
      });
    }
    try {
      await action();
    } catch (error) {
      if (mounted) setState(() => _error = _message(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      body: Stack(
        children: [
          ListView(
            key: const Key('sync-page'),
            padding: const EdgeInsets.all(AppUiTokens.pagePadding),
            children: [
              _header(),
              const SizedBox(height: AppUiTokens.sectionGap),
              _controls(),
              const SizedBox(height: AppUiTokens.compactGap),
              _scopeContext(),
              if (_error != null) ...[
                const SizedBox(height: AppUiTokens.sectionGap),
                MaterialBanner(
                  key: const Key('sync-error'),
                  content: Text(_error!),
                  actions: [
                    TextButton(
                      onPressed: () => setState(() => _error = null),
                      child: Text(context.l10n.syncHideError),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: AppUiTokens.sectionGap),
              if (_diff == null)
                Card(
                  key: const Key('sync-loading-diff'),
                  child: Padding(
                    padding: const EdgeInsets.all(AppUiTokens.pagePadding),
                    child: Text(context.l10n.syncCalculating),
                  ),
                )
              else ...[
                _summaryCard(_diff!),
                const SizedBox(height: AppUiTokens.sectionGap),
                _v0111Summary(_diff!),
                const SizedBox(height: AppUiTokens.sectionGap),
                _managedPlaylistsCard(),
                const SizedBox(height: AppUiTokens.sectionGap),
                _recoverySection(),
                const SizedBox(height: AppUiTokens.sectionGap),
                _details(_diff!),
              ],
            ],
          ),
          if (_busy)
            const Positioned(
              left: 0,
              right: 0,
              top: 0,
              child: LinearProgressIndicator(minHeight: 2),
            ),
        ],
      ),
    );
  }

  Widget _header() {
    final l10n = context.l10n;
    final colors = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l10n.syncTitle,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 4),
              Text(
                l10n.syncSubtitle,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: AppUiTokens.compactGap),
        IconButton(
          key: const Key('sync-refresh'),
          tooltip: l10n.syncRefresh,
          onPressed: _busy ? null : _refreshDiff,
          icon: const Icon(Icons.refresh),
        ),
      ],
    );
  }

  Widget _controls() {
    final l10n = context.l10n;
    final selectedKey = _scopeType == 'all'
        ? 'all|'
        : '$_scopeType|${_scopeId ?? ''}';
    final values = _scopes.map((scope) {
      final type = '${scope['type'] ?? 'all'}';
      final id = '${scope['id'] ?? ''}';
      return DropdownMenuItem<String>(
        value: '$type|$id',
        child: Text('${scope['title'] ?? id}', overflow: TextOverflow.ellipsis),
      );
    }).toList();
    final configured = _target['targetConfigured'] == true;
    final path = configured ? '${_target['targetPath'] ?? ''}' : '';

    Widget scopeField() => DropdownButtonFormField<String>(
      key: ValueKey('sync-scope-selector-$selectedKey'),
      initialValue: values.any((item) => item.value == selectedKey)
          ? selectedKey
          : null,
      isExpanded: true,
      items: values,
      onChanged: _busy
          ? null
          : (value) {
              if (value != null) _changeScope(value);
            },
      decoration: InputDecoration(
        labelText: l10n.syncScopeLabel,
        prefixIcon: const Icon(Icons.library_music_outlined),
        isDense: true,
      ),
    );

    Widget folderField() => InputDecorator(
      decoration: InputDecoration(
        labelText: l10n.syncFolderLabel,
        prefixIcon: const Icon(Icons.folder_outlined),
        isDense: true,
      ),
      child: Row(
        children: [
          Expanded(
            child: Tooltip(
              message: configured ? path : l10n.syncFolderNotSelected,
              child: Text(
                configured ? path : l10n.syncFolderNotSelected,
                key: const Key('sync-target-state'),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
          const SizedBox(width: AppUiTokens.compactGap),
          TextButton(
            key: const Key('sync-select-target'),
            onPressed: _busy ? null : _chooseTarget,
            child: Text(
              configured ? l10n.syncChangeFolder : l10n.syncChooseFolder,
            ),
          ),
        ],
      ),
    );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: LayoutBuilder(
          builder: (context, constraints) {
            if (constraints.maxWidth >= 900) {
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 4, child: scopeField()),
                  const SizedBox(width: AppUiTokens.sectionGap),
                  Expanded(flex: 6, child: folderField()),
                ],
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                scopeField(),
                const SizedBox(height: AppUiTokens.sectionGap),
                folderField(),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _summaryCard(Map<String, dynamic> diff) {
    final summary = _summary(diff);
    final ready = _int(summary['readyToDownload']);
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);
    final configured = _target['targetConfigured'] == true;
    final l10n = context.l10n;
    final colors = Theme.of(context).colorScheme;

    final title = ready > 0 && blockers == 0
        ? l10n.syncStatusReadyTitle
        : ready > 0
        ? l10n.syncStatusMixedTitle
        : queued > 0
        ? l10n.syncStatusQueuedTitle
        : blockers > 0
        ? l10n.syncStatusAttentionTitle
        : l10n.syncStatusCompleteTitle;
    final body = ready > 0
        ? blockers > 0
              ? '${l10n.syncReadyBody(ready)} ${l10n.syncAttentionBody(blockers)}'
              : l10n.syncReadyBody(ready)
        : queued > 0
        ? l10n.syncQueuedBody(queued)
        : blockers > 0
        ? l10n.syncAttentionBody(blockers)
        : l10n.syncStatusCompleteBody;
    final statusIcon = ready > 0 && blockers == 0
        ? Icons.check_circle_outline
        : ready > 0 || blockers > 0
        ? Icons.info_outline
        : queued > 0
        ? Icons.schedule
        : Icons.task_alt;
    final statusColor = ready > 0 && blockers == 0
        ? colors.primaryContainer
        : blockers > 0
        ? colors.tertiaryContainer
        : colors.secondaryContainer;

    return Card(
      key: const Key('sync-summary'),
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LayoutBuilder(
              builder: (context, constraints) {
                final status = Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: statusColor,
                        borderRadius: AppUiTokens.mediumRadius,
                      ),
                      child: Icon(statusIcon),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            key: const Key('sync-status-title'),
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            body,
                            key: const Key('sync-status-body'),
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(color: colors.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                  ],
                );

                final actions = Wrap(
                  spacing: AppUiTokens.compactGap,
                  runSpacing: AppUiTokens.compactGap,
                  alignment: WrapAlignment.end,
                  children: [
                    if (widget.onOpenDownloads != null)
                      OutlinedButton.icon(
                        key: const Key('sync-open-downloads'),
                        onPressed: _busy ? null : widget.onOpenDownloads,
                        icon: const Icon(Icons.download_outlined),
                        label: Text(l10n.syncOpenDownloads),
                      ),
                    FilledButton.icon(
                      key: const Key('sync-now'),
                      onPressed:
                          !_busy &&
                              (configured ||
                                  (ready == 0 &&
                                      _int(summary['readyToUpload']) > 0))
                          ? _synchronize
                          : null,
                      icon: const Icon(Icons.sync),
                      label: Text(
                        l10n.syncSynchronizeTracks(
                          ready + _int(summary['readyToUpload']),
                        ),
                      ),
                    ),
                  ],
                );

                if (constraints.maxWidth >= 980) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: status),
                      const SizedBox(width: AppUiTokens.sectionGap),
                      actions,
                    ],
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    status,
                    const SizedBox(height: 12),
                    Align(alignment: Alignment.centerLeft, child: actions),
                  ],
                );
              },
            ),
            const SizedBox(height: AppUiTokens.sectionGap),
            _coverage(summary),
            const SizedBox(height: AppUiTokens.sectionGap),
            _metrics(summary),
            const SizedBox(height: 12),
            const Divider(),
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.info_outline,
                  size: 18,
                  color: colors.onSurfaceVariant,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.syncSafetyNote,
                    key: const Key('sync-safety-note'),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _coverage(Map<String, dynamic> summary) {
    final l10n = context.l10n;
    final colors = Theme.of(context).colorScheme;
    final current = _percent(summary['currentCoveragePercent']);
    final projected = _percent(summary['projectedCoveragePercent']);
    final desired = _int(summary['desiredTracks']);
    final covered = _int(summary['alreadyCovered']);
    final projectedCovered = _projectedCovered(summary, desired, projected);

    return Column(
      key: const Key('sync-coverage'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                l10n.syncCoverageTitle,
                style: Theme.of(
                  context,
                ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
              ),
            ),
            if (projectedCovered != null)
              Text(
                l10n.syncCoverageTrackTransition(covered, projectedCovered),
                key: const Key('sync-coverage-track-transition'),
                style: Theme.of(context).textTheme.labelLarge,
              ),
          ],
        ),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: SizedBox(
            height: 10,
            child: Stack(
              fit: StackFit.expand,
              children: [
                LinearProgressIndicator(
                  value: projected / 100,
                  backgroundColor: colors.surfaceContainerHighest,
                  color: colors.secondaryContainer,
                ),
                LinearProgressIndicator(
                  value: current / 100,
                  backgroundColor: Colors.transparent,
                  color: colors.primary,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 7),
        Row(
          children: [
            Expanded(
              child: Text(
                l10n.syncCoverageCurrent(_formatPercent(current)),
                key: const Key('sync-coverage-current-label'),
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
              ),
            ),
            Text(
              l10n.syncCoverageProjected(_formatPercent(projected)),
              key: const Key('sync-coverage-projected-label'),
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
            ),
          ],
        ),
      ],
    );
  }

  Widget _metrics(Map<String, dynamic> summary) {
    final l10n = context.l10n;
    final entries = [
      _MetricData(
        keyName: 'yandex',
        label: l10n.syncMetricYandex,
        value: _int(summary['desiredTracks']),
        icon: Icons.cloud_outlined,
      ),
      _MetricData(
        keyName: 'local',
        label: l10n.syncMetricLocal,
        value: _int(summary['alreadyCovered']),
        icon: Icons.library_music_outlined,
      ),
      _MetricData(
        keyName: 'download',
        label: l10n.syncMetricDownload,
        value: _int(summary['readyToDownload']),
        icon: Icons.download_outlined,
        emphasized: true,
      ),
      _MetricData(
        keyName: 'queued',
        label: l10n.syncMetricQueued,
        value: _int(summary['alreadyQueued']),
        icon: Icons.schedule,
      ),
      _MetricData(
        keyName: 'attention',
        label: l10n.syncMetricAttention,
        value: _blockerCount(summary),
        icon: Icons.help_outline,
        attention: _blockerCount(summary) > 0,
      ),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        const gap = AppUiTokens.compactGap;
        final columns = constraints.maxWidth >= 1050
            ? 5
            : constraints.maxWidth >= 680
            ? 3
            : constraints.maxWidth >= 420
            ? 2
            : 1;
        final width = (constraints.maxWidth - gap * (columns - 1)) / columns;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: [
            for (final entry in entries)
              SizedBox(width: width, child: _metricCard(entry)),
          ],
        );
      },
    );
  }

  Widget _metricCard(_MetricData entry) {
    final colors = Theme.of(context).colorScheme;
    final background = entry.emphasized
        ? colors.primaryContainer
        : entry.attention
        ? colors.tertiaryContainer
        : colors.surfaceContainerLowest;
    final foreground = entry.emphasized
        ? colors.onPrimaryContainer
        : entry.attention
        ? colors.onTertiaryContainer
        : colors.onSurface;

    return Container(
      key: Key('sync-metric-${entry.keyName}'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: background,
        borderRadius: AppUiTokens.mediumRadius,
        border: Border.all(color: colors.outlineVariant),
      ),
      child: Row(
        children: [
          Icon(entry.icon, size: 20, color: foreground),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: foreground),
                ),
                const SizedBox(height: 4),
                Text(
                  '${entry.value}',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: foreground,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _details(Map<String, dynamic> diff) {
    final buckets = _OperationBuckets.fromOperations(_maps(diff['operations']));
    final filter = _planFilter ?? _defaultFilter(buckets);
    final items = buckets.itemsFor(filter);
    final l10n = context.l10n;
    final colors = Theme.of(context).colorScheme;

    return Card(
      key: const Key('sync-diff-details'),
      child: Padding(
        padding: const EdgeInsets.all(AppUiTokens.sectionGap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l10n.syncPlanTitle,
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        l10n.syncPlanScope(_selectedScopeTitle()),
                        key: const Key('sync-plan-scope'),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  l10n.syncPlanShown(items.length, buckets.total),
                  key: const Key('sync-plan-shown'),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _filterChip(SyncPlanFilter.all, filter, buckets.total),
                  const SizedBox(width: 8),
                  _filterChip(
                    SyncPlanFilter.download,
                    filter,
                    buckets.downloads.length,
                  ),
                  const SizedBox(width: 8),
                  _filterChip(
                    SyncPlanFilter.decision,
                    filter,
                    buckets.decisions.length,
                  ),
                  const SizedBox(width: 8),
                  _filterChip(
                    SyncPlanFilter.matching,
                    filter,
                    buckets.matching.length,
                  ),
                  const SizedBox(width: 8),
                  _filterChip(
                    SyncPlanFilter.variant,
                    filter,
                    buckets.variants.length,
                  ),
                  const SizedBox(width: 8),
                  _filterChip(
                    SyncPlanFilter.localOnly,
                    filter,
                    buckets.localOnly.length,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            const Divider(),
            if (items.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 28),
                child: Center(
                  child: Text(
                    l10n.syncNoOperations,
                    key: const Key('sync-plan-empty'),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                ),
              )
            else
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 900;
                  return Column(
                    children: [
                      if (wide) _tableHeader(),
                      for (final item in items) _operationRow(item, wide: wide),
                    ],
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _filterChip(SyncPlanFilter value, SyncPlanFilter selected, int count) {
    final l10n = context.l10n;
    final label = switch (value) {
      SyncPlanFilter.all => l10n.syncFilterAll(count),
      SyncPlanFilter.download => l10n.syncFilterDownload(count),
      SyncPlanFilter.decision => l10n.syncFilterDecision(count),
      SyncPlanFilter.matching => l10n.syncFilterMatching(count),
      SyncPlanFilter.variant => l10n.syncFilterVariant(count),
      SyncPlanFilter.localOnly => l10n.syncFilterLocalOnly(count),
    };
    return ChoiceChip(
      key: Key('sync-filter-${value.name}'),
      selected: selected == value,
      showCheckmark: false,
      label: Text(label),
      onSelected: (_) => setState(() => _planFilter = value),
    );
  }

  Widget _tableHeader() {
    final l10n = context.l10n;
    final colors = Theme.of(context).colorScheme;
    Text header(String value) => Text(
      value,
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
        color: colors.onSurfaceVariant,
        fontWeight: FontWeight.w700,
      ),
    );

    return Container(
      key: const Key('sync-plan-table-header'),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      color: colors.surfaceContainerLowest,
      child: Row(
        children: [
          Expanded(flex: 5, child: header(l10n.syncColumnTrack)),
          const SizedBox(width: 12),
          Expanded(flex: 2, child: header(l10n.syncColumnAction)),
          const SizedBox(width: 12),
          Expanded(flex: 3, child: header(l10n.syncColumnReason)),
          const SizedBox(width: 12),
          Expanded(flex: 2, child: header(l10n.syncColumnStatus)),
        ],
      ),
    );
  }

  Widget _operationRow(Map<String, dynamic> item, {required bool wide}) {
    final metadata = _metadata(item);
    final externalId = '${item['externalId'] ?? ''}';
    final type = '${item['type'] ?? ''}';
    final presentation = _operationPresentation(item);
    final keyPrefix = switch (type) {
      'enqueue_download' => 'sync-download',
      'user_decision_required' => 'sync-decision',
      'review_identity' => 'sync-review',
      'review_variant' => 'sync-variant',
      'local_only' => 'sync-local',
      _ => 'sync-operation',
    };

    final track = _trackCell(metadata);
    final action = Align(
      alignment: Alignment.centerLeft,
      child: Chip(
        visualDensity: VisualDensity.compact,
        avatar: Icon(presentation.icon, size: 16),
        label: Text(presentation.actionLabel),
      ),
    );
    final reason = Text(
      presentation.reason,
      style: Theme.of(context).textTheme.bodySmall,
    );
    final status = _operationStatus(item, presentation);

    if (wide) {
      return Container(
        key: Key('$keyPrefix-$externalId'),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
        ),
        child: Row(
          children: [
            Expanded(flex: 5, child: track),
            const SizedBox(width: 12),
            Expanded(flex: 2, child: action),
            const SizedBox(width: 12),
            Expanded(flex: 3, child: reason),
            const SizedBox(width: 12),
            Expanded(flex: 2, child: status),
          ],
        ),
      );
    }

    return Container(
      key: Key('$keyPrefix-$externalId'),
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          track,
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              action,
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: reason,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Align(alignment: Alignment.centerLeft, child: status),
        ],
      ),
    );
  }

  Widget _trackCell(Map<String, dynamic> metadata) {
    final colors = Theme.of(context).colorScheme;
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: colors.surfaceContainerHighest,
            borderRadius: AppUiTokens.smallRadius,
          ),
          child: Icon(Icons.music_note, color: colors.onSurfaceVariant),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _trackTitle(metadata),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 2),
              Text(
                _trackArtists(metadata),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _operationStatus(
    Map<String, dynamic> item,
    _OperationPresentation presentation,
  ) {
    final type = '${item['type'] ?? ''}';
    final id = '${item['externalId'] ?? ''}';
    final l10n = context.l10n;

    if (type == 'user_decision_required') {
      return Wrap(
        spacing: 4,
        runSpacing: 4,
        children: [
          TextButton(
            onPressed: _busy ? null : () => _setAction(id, 'wanted'),
            child: Text(l10n.syncDownloadAction),
          ),
          TextButton(
            onPressed: _busy ? null : () => _setAction(id, 'ignored'),
            child: Text(l10n.syncIgnoreAction),
          ),
        ],
      );
    }
    if (type == 'review_identity' && widget.onOpenMatching != null) {
      return TextButton(
        onPressed: _busy ? null : widget.onOpenMatching,
        child: Text(l10n.syncOpenMatching),
      );
    }
    if (type == 'review_variant' && widget.onOpenMatching != null) {
      return TextButton(
        onPressed: _busy ? null : widget.onOpenMatching,
        child: Text(l10n.syncCheckVariant),
      );
    }
    return Text(
      presentation.statusLabel,
      style: Theme.of(context).textTheme.bodySmall,
    );
  }

  _OperationPresentation _operationPresentation(Map<String, dynamic> item) {
    final l10n = context.l10n;
    final metadata = _metadata(item);
    final type = '${item['type'] ?? ''}';
    switch (type) {
      case 'enqueue_download':
        return _OperationPresentation(
          actionLabel: l10n.syncActionDownload,
          reason: l10n.syncReasonWillQueue,
          statusLabel: l10n.syncStatusReady,
          icon: Icons.download_outlined,
        );
      case 'user_decision_required':
        return _OperationPresentation(
          actionLabel: l10n.syncActionDecision,
          reason: l10n.syncReasonMissing,
          statusLabel: l10n.syncActionDecision,
          icon: Icons.help_outline,
        );
      case 'review_identity':
        final required = item['reason'] == 'matching_required';
        return _OperationPresentation(
          actionLabel: l10n.syncActionMatching,
          reason: required
              ? l10n.syncReasonMatchingRequired
              : l10n.syncReasonMatchingReview,
          statusLabel: l10n.syncActionMatching,
          icon: Icons.compare_arrows,
        );
      case 'review_variant':
        final rawVariant =
            '${metadata['variantStatus'] ?? item['reason'] ?? ''}';
        return _OperationPresentation(
          actionLabel: l10n.syncActionVariant,
          reason: l10n.syncReasonVariant(_variantLabel(rawVariant)),
          statusLabel: l10n.syncActionVariant,
          icon: Icons.rule_outlined,
        );
      case 'local_only':
        final outside = item['reason'] == 'outside_selected_scope';
        return _OperationPresentation(
          actionLabel: l10n.syncActionLocalOnly,
          reason: outside
              ? l10n.syncReasonOutsideScope
              : l10n.syncReasonLocalOnly,
          statusLabel: l10n.syncStatusInformational,
          icon: Icons.folder_outlined,
        );
      default:
        return _OperationPresentation(
          actionLabel: l10n.syncStatusInformational,
          reason: '${item['reason'] ?? ''}',
          statusLabel: l10n.syncStatusInformational,
          icon: Icons.info_outline,
        );
    }
  }

  String _variantLabel(String raw) {
    final l10n = context.l10n;
    return switch (raw) {
      'same' => l10n.matchingVariantSame,
      'altered' => l10n.matchingVariantAltered,
      'different_version' ||
      'variant_different_version' => l10n.matchingVariantDifferent,
      'uncertain' => l10n.matchingVariantUncertain,
      'not_checked' => l10n.matchingVariantNotChecked,
      _ => raw.isEmpty ? l10n.matchingVariantNotChecked : raw,
    };
  }

  SyncPlanFilter _defaultFilter(_OperationBuckets buckets) {
    if (buckets.downloads.isNotEmpty) return SyncPlanFilter.download;
    if (buckets.decisions.isNotEmpty) return SyncPlanFilter.decision;
    if (buckets.matching.isNotEmpty) return SyncPlanFilter.matching;
    if (buckets.variants.isNotEmpty) return SyncPlanFilter.variant;
    return SyncPlanFilter.all;
  }

  String _selectedScopeTitle() {
    for (final scope in _scopes) {
      if ('${scope['type'] ?? ''}' == _scopeType &&
          _nullableString(scope['id']) == _scopeId) {
        return '${scope['title'] ?? _scopeId ?? context.l10n.syncAllLibrary}';
      }
    }
    return _scopeId ?? context.l10n.syncAllLibrary;
  }

  String _trackTitle(Map<String, dynamic> metadata) {
    final title = '${metadata['title'] ?? ''}'.trim();
    return title.isEmpty ? context.l10n.syncUnknownTrack : title;
  }

  String _trackArtists(Map<String, dynamic> metadata) {
    final rawArtists = metadata['artists'];
    final artists = rawArtists is List
        ? rawArtists
              .map((e) => '$e'.trim())
              .where((e) => e.isNotEmpty)
              .join(', ')
        : '';
    return artists.isEmpty ? context.l10n.syncUnknownArtist : artists;
  }

  String _formatPercent(double value) {
    final text = value == value.roundToDouble()
        ? value.toStringAsFixed(0)
        : value.toStringAsFixed(1);
    return Localizations.localeOf(context).languageCode == 'ru'
        ? text.replaceAll('.', ',')
        : text;
  }

  static int? _projectedCovered(
    Map<String, dynamic> summary,
    int desired,
    double projectedPercent,
  ) {
    for (final key in const ['projectedCovered', 'projectedCoveredTracks']) {
      final value = summary[key];
      if (value != null) return _int(value);
    }
    if (desired > 0 && projectedPercent >= 99.999) return desired;
    return null;
  }

  static bool _scopeExists(
    List<Map<String, dynamic>> scopes,
    String type,
    String? id,
  ) {
    return scopes.any(
      (scope) =>
          '${scope['type'] ?? ''}' == type &&
          _nullableString(scope['id']) == id,
    );
  }

  static int _blockerCount(Map<String, dynamic> summary) =>
      _int(summary['missingUndecided']) +
      _int(summary['identityReview']) +
      _int(summary['notAnalyzed']) +
      _int(summary['variantIssues']);

  static Map<String, dynamic> _summary(Map<String, dynamic> diff) {
    final value = diff['summary'];
    return value is Map ? Map<String, dynamic>.from(value) : const {};
  }

  static Map<String, dynamic> _metadata(Map<String, dynamic> operation) {
    final value = operation['metadata'];
    return value is Map ? Map<String, dynamic>.from(value) : const {};
  }

  static int _int(Object? value) =>
      value is num ? value.toInt() : int.tryParse('$value') ?? 0;

  static double _percent(Object? value) {
    final parsed = value is num
        ? value.toDouble()
        : double.tryParse('$value') ?? 0;
    return parsed.clamp(0, 100).toDouble();
  }

  static String? _nullableString(Object? value) {
    if (value == null) return null;
    final text = '$value'.trim();
    return text.isEmpty || text == 'null' ? null : text;
  }

  static List<Map<String, dynamic>> _maps(Object? value) => value is List
      ? value
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList()
      : <Map<String, dynamic>>[];

  static String _message(Object error) =>
      error is SyncBridgeException ? error.message : error.toString();
}

class _MetricData {
  const _MetricData({
    required this.keyName,
    required this.label,
    required this.value,
    required this.icon,
    this.emphasized = false,
    this.attention = false,
  });

  final String keyName;
  final String label;
  final int value;
  final IconData icon;
  final bool emphasized;
  final bool attention;
}

class _OperationPresentation {
  const _OperationPresentation({
    required this.actionLabel,
    required this.reason,
    required this.statusLabel,
    required this.icon,
  });

  final String actionLabel;
  final String reason;
  final String statusLabel;
  final IconData icon;
}

class _OperationBuckets {
  const _OperationBuckets({
    required this.all,
    required this.downloads,
    required this.decisions,
    required this.matching,
    required this.variants,
    required this.localOnly,
  });

  factory _OperationBuckets.fromOperations(
    List<Map<String, dynamic>> operations,
  ) {
    return _OperationBuckets(
      all: operations,
      downloads: operations
          .where((item) => item['type'] == 'enqueue_download')
          .toList(),
      decisions: operations
          .where((item) => item['type'] == 'user_decision_required')
          .toList(),
      matching: operations
          .where((item) => item['type'] == 'review_identity')
          .toList(),
      variants: operations
          .where((item) => item['type'] == 'review_variant')
          .toList(),
      localOnly: operations
          .where((item) => item['type'] == 'local_only')
          .toList(),
    );
  }

  final List<Map<String, dynamic>> all;
  final List<Map<String, dynamic>> downloads;
  final List<Map<String, dynamic>> decisions;
  final List<Map<String, dynamic>> matching;
  final List<Map<String, dynamic>> variants;
  final List<Map<String, dynamic>> localOnly;

  int get total => all.length;

  List<Map<String, dynamic>> itemsFor(SyncPlanFilter filter) =>
      switch (filter) {
        SyncPlanFilter.all => all,
        SyncPlanFilter.download => downloads,
        SyncPlanFilter.decision => decisions,
        SyncPlanFilter.matching => matching,
        SyncPlanFilter.variant => variants,
        SyncPlanFilter.localOnly => localOnly,
      };
}
