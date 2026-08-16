import 'package:flutter/material.dart';

import 'folder_picker.dart';
import 'sync_bridge.dart';

class SyncPage extends StatefulWidget {
  const SyncPage({
    super.key,
    required this.bridge,
    this.folderPicker = const SystemLocalFolderPicker(),
    this.onOpenDownloads,
    this.onOpenMatching,
  });

  final SyncBridgeClient bridge;
  final LocalFolderPicker folderPicker;
  final VoidCallback? onOpenDownloads;
  final VoidCallback? onOpenMatching;

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
      ]);
      if (!mounted) return;

      final scopes = _maps(results[0]['items']);
      final target = Map<String, dynamic>.from(results[1]);
      final rawCurrent = results[2]['plan'];
      final current =
          rawCurrent is Map ? Map<String, dynamic>.from(rawCurrent) : null;

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
        _diff = _currentCanBeShown(current, scopeType, scopeId) ? current : null;
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
    final nextId =
        parts.length > 1 && parts[1].isNotEmpty ? parts[1] : null;
    if (nextType == _scopeType && nextId == _scopeId) return;
    setState(() {
      _scopeType = nextType;
      _scopeId = nextId;
      _diff = null;
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
    if (_target['targetConfigured'] != true) {
      setState(() => _error = 'Сначала выберите папку для загрузок.');
      return;
    }

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
    final queued = _int(summary['alreadyQueued']);
    final blockers = _blockerCount(summary);

    if (downloads == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            queued > 0
                ? 'Новых загрузок нет: нужные треки уже находятся в очереди.'
                : blockers > 0
                    ? 'Сейчас нечего скачивать. Сначала разберите треки, требующие решения или сопоставления.'
                    : 'Синхронизация не требует новых загрузок.',
          ),
        ),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        key: const Key('sync-confirmation'),
        title: const Text('Синхронизировать?'),
        content: Text(
          'В очередь загрузок будет добавлено: $downloads.\n\n'
          'Существующие локальные файлы не удаляются, не перемещаются и не изменяются. '
          'Коллекция Яндекс Музыки также не изменяется.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            key: const Key('sync-confirm'),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Синхронизировать'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    Map<String, dynamic>? result;
    await _run(() async {
      result = await widget.bridge.apply('${fresh!['id']}', confirm: true);
      _diff = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
    });
    if (!mounted || result == null) return;

    final rawResult = result!['result'];
    final data = rawResult is Map
        ? Map<String, dynamic>.from(rawResult)
        : const <String, dynamic>{};
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Добавлено в очередь: ${_int(data['enqueued'])}. '
          'Пропущено: ${_int(data['skipped'])}. Ошибок: ${_int(data['failed'])}.',
        ),
        action: widget.onOpenDownloads == null
            ? null
            : SnackBarAction(
                label: 'Загрузки',
                onPressed: widget.onOpenDownloads!,
              ),
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Синхронизация'),
        actions: [
          IconButton(
            key: const Key('sync-refresh'),
            tooltip: 'Обновить список',
            onPressed: _busy ? null : _refreshDiff,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              key: const Key('sync-page'),
              padding: const EdgeInsets.all(20),
              children: [
                _controls(),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  MaterialBanner(
                    key: const Key('sync-error'),
                    content: Text(_error!),
                    actions: [
                      TextButton(
                        onPressed: () => setState(() => _error = null),
                        child: const Text('Скрыть'),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 16),
                if (_diff == null)
                  const Card(
                    key: Key('sync-loading-diff'),
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'Считаем разницу между Яндекс Музыкой и локальной библиотекой…',
                      ),
                    ),
                  )
                else ...[
                  _summaryCard(_diff!),
                  const SizedBox(height: 12),
                  _mainActions(_diff!),
                  const SizedBox(height: 12),
                  _details(_diff!),
                ],
              ],
            ),
    );
  }

  Widget _controls() {
    final selectedKey =
        _scopeType == 'all' ? 'all|' : '$_scopeType|${_scopeId ?? ''}';
    final values = _scopes.map((scope) {
      final type = '${scope['type'] ?? 'all'}';
      final id = '${scope['id'] ?? ''}';
      return DropdownMenuItem<String>(
        value: '$type|$id',
        child: Text(
          '${scope['title'] ?? id}',
          overflow: TextOverflow.ellipsis,
        ),
      );
    }).toList();
    final configured = _target['targetConfigured'] == true;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Что синхронизировать',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              key: ValueKey('sync-scope-selector-$selectedKey'),
              initialValue: values.any((item) => item.value == selectedKey)
                  ? selectedKey
                  : null,
              items: values,
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value != null) _changeScope(value);
                    },
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Куда скачивать недостающие треки',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            Text(
              configured ? '${_target['targetPath']}' : 'Папка не выбрана.',
              key: const Key('sync-target-state'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('sync-select-target'),
              onPressed: _busy ? null : _chooseTarget,
              icon: const Icon(Icons.folder_open),
              label: Text(configured ? 'Изменить папку' : 'Выбрать папку'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _summaryCard(Map<String, dynamic> diff) {
    final summary = _summary(diff);
    final scope = _selectedScopeTitle();
    final matching =
        _int(summary['identityReview']) + _int(summary['notAnalyzed']);

    Widget metric(String label, int value, IconData icon) => SizedBox(
          width: 220,
          child: ListTile(
            dense: true,
            leading: Icon(icon, size: 20),
            title: Text(label),
            trailing: Text(
              '$value',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        );

    return Card(
      key: const Key('sync-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Разница: $scope',
              key: const Key('sync-diff-title'),
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                metric(
                  'В Яндекс Музыке',
                  _int(summary['desiredTracks']),
                  Icons.cloud_outlined,
                ),
                metric(
                  'Уже локально',
                  _int(summary['alreadyCovered']),
                  Icons.library_music_outlined,
                ),
                metric(
                  'К скачиванию',
                  _int(summary['readyToDownload']),
                  Icons.download_outlined,
                ),
                metric(
                  'Уже в очереди',
                  _int(summary['alreadyQueued']),
                  Icons.schedule,
                ),
                metric(
                  'Нужно решить',
                  _int(summary['missingUndecided']),
                  Icons.help_outline,
                ),
                metric(
                  'Нужно сопоставить',
                  matching,
                  Icons.compare_arrows,
                ),
                metric(
                  'Проверить версию',
                  _int(summary['variantIssues']),
                  Icons.rule_outlined,
                ),
              ],
            ),
            const Divider(),
            Text(
              'Сейчас локально: ${summary['currentCoveragePercent'] ?? 0}% · '
              'после успешных загрузок: ${summary['projectedCoveragePercent'] ?? 0}%',
              key: const Key('sync-coverage'),
            ),
            if (_blockerCount(summary) > 0) ...[
              const SizedBox(height: 6),
              Text(
                '${_blockerCount(summary)} треков требуют решения или проверки и пока не будут скачаны автоматически.',
                key: const Key('sync-blockers'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _mainActions(Map<String, dynamic> diff) {
    final summary = _summary(diff);
    final ready = _int(summary['readyToDownload']);
    final configured = _target['targetConfigured'] == true;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          key: const Key('sync-now'),
          onPressed: !_busy && configured ? _synchronize : null,
          icon: const Icon(Icons.sync),
          label: Text(
            ready > 0 ? 'Синхронизировать ($ready)' : 'Синхронизировать',
          ),
        ),
        if (widget.onOpenDownloads != null)
          TextButton.icon(
            key: const Key('sync-open-downloads'),
            onPressed: widget.onOpenDownloads,
            icon: const Icon(Icons.download_outlined),
            label: const Text('Открыть загрузки'),
          ),
      ],
    );
  }

  Widget _details(Map<String, dynamic> diff) {
    final operations = _maps(diff['operations']);
    final downloads = operations
        .where((item) => item['type'] == 'enqueue_download')
        .toList();
    final decisions = operations
        .where((item) => item['type'] == 'user_decision_required')
        .toList();
    final matching =
        operations.where((item) => item['type'] == 'review_identity').toList();
    final variants =
        operations.where((item) => item['type'] == 'review_variant').toList();
    final localOnly =
        operations.where((item) => item['type'] == 'local_only').toList();

    return Card(
      key: const Key('sync-diff-details'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            _group(
              'Будет скачано',
              downloads,
              _downloadRow,
              initiallyExpanded: downloads.isNotEmpty,
            ),
            _group(
              'Нужно решить',
              decisions,
              _decisionRow,
              initiallyExpanded: decisions.isNotEmpty,
            ),
            _group(
              'Нужно сопоставить',
              matching,
              _matchingRow,
              initiallyExpanded: matching.isNotEmpty && downloads.isEmpty,
            ),
            _group('Проверить версию', variants, _variantRow),
            _group(
              'Только локально / вне выбранной области',
              localOnly,
              _infoRow,
            ),
          ],
        ),
      ),
    );
  }

  Widget _group(
    String title,
    List<Map<String, dynamic>> items,
    Widget Function(Map<String, dynamic>) row, {
    bool initiallyExpanded = false,
  }) {
    return ExpansionTile(
      key: Key('sync-group-$title'),
      initiallyExpanded: initiallyExpanded,
      title: Text('$title (${items.length})'),
      children: items.isEmpty
          ? const [ListTile(title: Text('Нет'))]
          : items.map(row).toList(),
    );
  }

  Widget _downloadRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    return ListTile(
      key: Key('sync-download-${item['externalId']}'),
      leading: const Icon(Icons.download_outlined),
      title: Text(_trackTitle(metadata)),
      subtitle: const Text('Будет добавлен в очередь загрузок'),
    );
  }

  Widget _decisionRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    final id = '${item['externalId'] ?? ''}';
    return ListTile(
      key: Key('sync-decision-$id'),
      title: Text(_trackTitle(metadata)),
      subtitle: const Text('Трек отсутствует локально'),
      trailing: Wrap(
        spacing: 4,
        children: [
          TextButton(
            onPressed: _busy ? null : () => _setAction(id, 'wanted'),
            child: const Text('Скачать'),
          ),
          TextButton(
            onPressed: _busy ? null : () => _setAction(id, 'ignored'),
            child: const Text('Игнорировать'),
          ),
        ],
      ),
    );
  }

  Widget _matchingRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    final required = item['reason'] == 'matching_required';
    return ListTile(
      key: Key('sync-review-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text(
        required
            ? 'Ещё не проверялся по локальной библиотеке'
            : 'Сопоставление требует проверки',
      ),
      trailing: widget.onOpenMatching == null
          ? null
          : TextButton(
              onPressed: widget.onOpenMatching,
              child: const Text('Открыть сопоставление'),
            ),
    );
  }

  Widget _variantRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    final variant = '${metadata['variantStatus'] ?? item['reason'] ?? ''}';
    return ListTile(
      key: Key('sync-variant-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text(
        'Локальный трек найден, но версия требует проверки: $variant',
      ),
      trailing: widget.onOpenMatching == null
          ? null
          : TextButton(
              onPressed: widget.onOpenMatching,
              child: const Text('Проверить'),
            ),
    );
  }

  Widget _infoRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    return ListTile(
      key: Key('sync-local-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text(
        item['reason'] == 'outside_selected_scope'
            ? 'Есть локально, но не относится к выбранной области'
            : 'Есть только локально',
      ),
    );
  }

  String _selectedScopeTitle() {
    for (final scope in _scopes) {
      if ('${scope['type'] ?? ''}' == _scopeType &&
          _nullableString(scope['id']) == _scopeId) {
        return '${scope['title'] ?? _scopeId ?? 'Вся библиотека'}';
      }
    }
    return _scopeId ?? 'Вся библиотека';
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

  static String _trackTitle(Map<String, dynamic> metadata) {
    final rawArtists = metadata['artists'];
    final artists = rawArtists is List
        ? rawArtists.map((e) => '$e').where((e) => e.isNotEmpty).join(', ')
        : '';
    final title = '${metadata['title'] ?? ''}';
    return artists.isEmpty ? title : '$artists — $title';
  }

  static int _int(Object? value) =>
      value is num ? value.toInt() : int.tryParse('$value') ?? 0;

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
