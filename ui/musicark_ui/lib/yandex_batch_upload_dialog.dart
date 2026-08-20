import 'dart:async';

import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'scope_context_bar.dart';
import 'v0111_localizations_ext.dart';
import 'yandex_batch_upload_bridge.dart';
import 'yandex_upload_bridge.dart';

Future<Map<String, dynamic>?> showYandexBatchUploadDialog({
  required BuildContext context,
  required List<Map<String, dynamic>> tracks,
  required YandexUploadBridgeClient targetBridge,
  required YandexBatchUploadBridgeClient batchBridge,
  required String localContext,
  String? localContextTooltip,
}) => showDialog<Map<String, dynamic>>(
  context: context,
  barrierDismissible: false,
  builder: (_) => YandexBatchUploadDialog(
    tracks: tracks,
    targetBridge: targetBridge,
    batchBridge: batchBridge,
    localContext: localContext,
    localContextTooltip: localContextTooltip,
  ),
);

class YandexBatchUploadDialog extends StatefulWidget {
  const YandexBatchUploadDialog({
    super.key,
    required this.tracks,
    required this.targetBridge,
    required this.batchBridge,
    required this.localContext,
    this.localContextTooltip,
  });

  final List<Map<String, dynamic>> tracks;
  final YandexUploadBridgeClient targetBridge;
  final YandexBatchUploadBridgeClient batchBridge;
  final String localContext;
  final String? localContextTooltip;

  @override
  State<YandexBatchUploadDialog> createState() => _YandexBatchUploadDialogState();
}

class _YandexBatchUploadDialogState extends State<YandexBatchUploadDialog> {
  bool _loading = true;
  bool _running = false;
  bool _rights = false;
  String? _error;
  String? _selectedKind;
  String? _batchId;
  int _completed = 0;
  int _total = 0;
  List<YandexUploadTarget> _targets = const [];
  Map<String, dynamic> _managed = const {};
  Map<String, dynamic>? _result;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  List<int> get _ids => widget.tracks
      .map((track) => int.tryParse('${track['id']}'))
      .whereType<int>()
      .toList(growable: false);

  int get _mp3Count => widget.tracks.where(_isMp3).length;
  int get _unsupportedCount => widget.tracks.length - _mp3Count;
  int get _bytes => widget.tracks.fold<int>(
    0,
    (sum, track) => sum + (int.tryParse('${track['fileSize'] ?? 0}') ?? 0),
  );

  bool _isMp3(Map<String, dynamic> track) {
    final extension = '${track['extension'] ?? ''}'.trim().toLowerCase();
    final fileName = '${track['fileName'] ?? ''}'.trim().toLowerCase();
    return extension == '.mp3' || extension == 'mp3' || fileName.endsWith('.mp3');
  }

  Future<void> _load() async {
    try {
      final values = await Future.wait([
        widget.targetBridge.targets(),
        widget.batchBridge.managedPlaylists(),
      ]);
      if (!mounted) return;
      final targets = values[0] as YandexUploadTargets;
      final managed = Map<String, dynamic>.from(values[1] as Map);
      String? selected;
      final roles = (managed['roles'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item));
      for (final role in roles) {
        if (role['role'] == 'uploaded' && role['configured'] == true) {
          final candidate = '${role['playlistKind'] ?? ''}'.trim();
          if (targets.playlists.any((item) => item.playlistKind == candidate)) {
            selected = candidate;
          }
        }
      }
      selected ??= targets.playlists.isEmpty ? null : targets.playlists.first.playlistKind;
      setState(() {
        _targets = targets.playlists;
        _managed = managed;
        _selectedKind = selected;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'load_failed';
      });
    }
  }

  String _sizeLabel() {
    if (_bytes <= 0) return '—';
    final mb = _bytes / (1024 * 1024);
    return mb >= .1 ? '${mb.toStringAsFixed(1)} MB' : '${(_bytes / 1024).toStringAsFixed(0)} KB';
  }

  String _newBatchId() =>
      'ui-${DateTime.now().microsecondsSinceEpoch}-${_ids.fold<int>(17, (value, id) => value * 31 + id)}';

  Future<void> _start({List<int>? retryIds}) async {
    final kind = _selectedKind;
    final ids = retryIds ?? _ids;
    if (_running || !_rights || kind == null || ids.isEmpty) return;
    final batchId = _newBatchId();
    setState(() {
      _running = true;
      _error = null;
      _result = null;
      _batchId = batchId;
      _completed = 0;
      _total = ids.length;
    });
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(milliseconds: 450), (_) => _pollStatus(batchId));
    try {
      final result = await widget.batchBridge.uploadBatch(
        localFileIds: ids,
        playlistKind: kind,
        confirm: true,
        rightsConfirmed: true,
        batchId: batchId,
      );
      if (!mounted) return;
      _poll?.cancel();
      setState(() {
        _result = Map<String, dynamic>.from(result);
        _completed = int.tryParse('${result['completed'] ?? ids.length}') ?? ids.length;
        _total = int.tryParse('${result['total'] ?? ids.length}') ?? ids.length;
        _running = false;
      });
    } catch (_) {
      if (!mounted) return;
      _poll?.cancel();
      setState(() {
        _error = 'upload_failed';
        _running = false;
      });
    }
  }

  Future<void> _pollStatus(String batchId) async {
    if (!_running || _batchId != batchId) return;
    try {
      final status = await widget.batchBridge.batchStatus(batchId);
      if (!mounted || _batchId != batchId) return;
      setState(() {
        _completed = int.tryParse('${status['completed'] ?? _completed}') ?? _completed;
        _total = int.tryParse('${status['total'] ?? _total}') ?? _total;
      });
    } catch (_) {
      // Polling is presentation-only. The authoritative upload invocation still
      // returns the final aggregate result.
    }
  }

  Future<void> _cancel() async {
    final batchId = _batchId;
    if (!_running || batchId == null) return;
    try {
      await widget.batchBridge.cancelBatch(batchId);
    } catch (_) {
      if (mounted) setState(() => _error = 'cancel_failed');
    }
  }

  Map<String, dynamic> get _counts {
    final raw = _result?['counts'];
    return raw is Map ? Map<String, dynamic>.from(raw) : const {};
  }

  List<int> get _retryable {
    final raw = _result?['retryableLocalFileIds'];
    if (raw is! List) return const [];
    return raw.map((value) => int.tryParse('$value')).whereType<int>().toList(growable: false);
  }

  List<int> get _manualCheck {
    final raw = _result?['manualCheckLocalFileIds'];
    if (raw is! List) return const [];
    return raw.map((value) => int.tryParse('$value')).whereType<int>().toList(growable: false);
  }

  int _count(String key) => int.tryParse('${_counts[key] ?? 0}') ?? 0;

  Widget _stat(String label, String value) => Expanded(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 2),
        Text(value, style: Theme.of(context).textTheme.titleSmall),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final hasResult = _result != null;
    return AlertDialog(
      key: const Key('yandex-batch-upload-dialog'),
      title: Text(l10n.v0111BulkUploadTitle(widget.tracks.length)),
      content: SizedBox(
        width: 680,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ScopeContextBar(
                collection: l10n.localLibraryTitle,
                localFolders: widget.localContext,
                localFoldersTooltip: widget.localContextTooltip,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  _stat(l10n.v0111TrackCount, '${widget.tracks.length}'),
                  _stat(l10n.v0111TotalSize, _sizeLabel()),
                  _stat(l10n.v0111Mp3Count, '$_mp3Count'),
                  _stat(l10n.v0111UnsupportedCount, '$_unsupportedCount'),
                ],
              ),
              const SizedBox(height: 16),
              if (_loading)
                const Center(child: CircularProgressIndicator())
              else if (_targets.isEmpty)
                Text(l10n.yandexUploadNoPlaylists)
              else
                DropdownButtonFormField<String>(
                  key: const Key('yandex-batch-playlist'),
                  initialValue: _selectedKind,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: l10n.v0111TargetPlaylist,
                    border: const OutlineInputBorder(),
                  ),
                  items: _targets
                      .map(
                        (target) => DropdownMenuItem<String>(
                          value: target.playlistKind,
                          child: Text(target.title, overflow: TextOverflow.ellipsis),
                        ),
                      )
                      .toList(growable: false),
                  onChanged: _running || hasResult
                      ? null
                      : (value) => setState(() => _selectedKind = value),
                ),
              const SizedBox(height: 8),
              CheckboxListTile(
                key: const Key('yandex-batch-rights'),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                value: _rights,
                onChanged: _running || hasResult
                    ? null
                    : (value) => setState(() => _rights = value == true),
                title: Text(l10n.v0111BatchRights),
              ),
              if (_running) ...[
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: _total > 0 ? (_completed / _total).clamp(0.0, 1.0) : null,
                ),
                const SizedBox(height: 6),
                Text(
                  l10n.v0111BatchProgress(_completed, _total),
                  key: const Key('yandex-batch-progress'),
                ),
              ],
              if (hasResult) ...[
                const SizedBox(height: 12),
                Card(
                  key: const Key('yandex-batch-result'),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${_result!['status']}' == 'cancelled'
                              ? l10n.v0111BatchCancelled
                              : _count('failed') > 0
                              ? l10n.v0111BatchFailed
                              : l10n.v0111BatchFinished,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 14,
                          runSpacing: 6,
                          children: [
                            Text('${l10n.v0111Verified}: ${_count('verified')}'),
                            Text('${l10n.v0111Processing}: ${_count('processing')}'),
                            Text('${l10n.v0111DeliveryUnknown}: ${_count('deliveryUnknown')}'),
                            Text('${l10n.v0111Failed}: ${_count('failed')}'),
                            Text('${l10n.v0111Skipped}: ${_count('skipped')}'),
                            Text('${l10n.v0111Cancelled}: ${_count('cancelled')}'),
                          ],
                        ),
                        if (_manualCheck.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            '${l10n.v0111CheckPlaylist}: ${_manualCheck.length}',
                            key: const Key('yandex-batch-manual-check'),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(
                  l10n.yandexUploadNetworkError,
                  key: const Key('yandex-batch-error'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              // Keep the managed state in the dialog's dependency graph so the
              // default role selection is testable without exposing numeric kinds.
              if (_managed.isEmpty) const SizedBox.shrink(),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _running ? null : () => Navigator.pop(context, _result),
          child: Text(hasResult ? l10n.close : l10n.cancel),
        ),
        if (_running)
          OutlinedButton.icon(
            key: const Key('yandex-batch-cancel'),
            onPressed: _cancel,
            icon: const Icon(Icons.stop_circle_outlined),
            label: Text(l10n.v0111CancelRemaining),
          )
        else if (hasResult && _retryable.isNotEmpty)
          FilledButton.tonalIcon(
            key: const Key('yandex-batch-retry-failures'),
            onPressed: () => _start(retryIds: _retryable),
            icon: const Icon(Icons.refresh),
            label: Text(l10n.v0111RetryFailures),
          )
        else if (!hasResult)
          FilledButton.icon(
            key: const Key('yandex-batch-submit'),
            onPressed: !_loading && _selectedKind != null && _rights ? () => _start() : null,
            icon: const Icon(Icons.cloud_upload_outlined),
            label: Text(l10n.v0111UploadToYandex),
          ),
      ],
    );
  }
}
