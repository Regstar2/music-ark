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
  Map<String, dynamic>? _plan;
  List<Map<String, dynamic>> _history = const [];
  String _scopeType = 'all';
  String? _scopeId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) setState(() => _loading = true);
    try {
      final results = await Future.wait([
        widget.bridge.scopes(),
        widget.bridge.target(),
        widget.bridge.current(),
        widget.bridge.history(),
      ]);
      if (!mounted) return;
      final rawPlan = results[2]['plan'];
      setState(() {
        _scopes = _maps(results[0]['items']);
        _target = Map<String, dynamic>.from(results[1]);
        _plan = rawPlan is Map ? Map<String, dynamic>.from(rawPlan) : null;
        _history = _maps(results[3]['items']);
        _error = null;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = _message(error);
      });
    }
  }

  Future<void> _chooseTarget() async {
    final path = await widget.folderPicker.pickDirectory();
    if (path == null || path.trim().isEmpty) return;
    await _run(() async {
      _target = await widget.bridge.setTarget(path);
      if (_plan != null) {
        _plan = await widget.bridge.plan('${_plan!['id']}');
      }
    });
  }

  Future<void> _createPlan() async {
    await _run(() async {
      _plan = await widget.bridge.createPlan(
        scopeType: _scopeType,
        scopeId: _scopeType == 'all' ? null : _scopeId,
      );
      _history = _maps((await widget.bridge.history())['items']);
    });
  }

  Future<void> _refreshPlan() async {
    final plan = _plan;
    if (plan == null) return;
    await _run(() async {
      _plan = await widget.bridge.plan('${plan['id']}');
      _history = _maps((await widget.bridge.history())['items']);
    });
  }

  Future<void> _cancelPlan() async {
    final plan = _plan;
    if (plan == null) return;
    await _run(() async {
      _plan = await widget.bridge.cancel('${plan['id']}');
      _history = _maps((await widget.bridge.history())['items']);
    });
  }

  Future<void> _setAction(String externalId, String action) async {
    await _run(() async {
      await widget.bridge.setAction(externalId, action);
      if (_plan != null) {
        _plan = await widget.bridge.plan('${_plan!['id']}');
      }
    });
  }

  Future<void> _apply() async {
    final plan = _plan;
    if (plan == null) return;
    final summary = _summary(plan);
    final downloads = _int(summary['readyToDownload']);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        key: const Key('sync-apply-confirmation'),
        title: const Text('Применить Sync Plan?'),
        content: Text(
          'Поставить $downloads треков в очередь загрузок?\n\n'
          'Никакие существующие локальные файлы не будут удалены, переименованы или изменены. '
          'Яндекс-библиотека также не изменяется.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            key: const Key('sync-confirm-apply'),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Поставить в очередь'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _run(() async {
      final result = await widget.bridge.apply('${plan['id']}', confirm: true);
      final rawPlan = result['plan'];
      if (rawPlan is Map) _plan = Map<String, dynamic>.from(rawPlan);
      _history = _maps((await widget.bridge.history())['items']);
    });
    if (!mounted || _plan == null) return;
    final result = _plan!['result'];
    final data = result is Map ? Map<String, dynamic>.from(result) : const <String, dynamic>{};
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'В очередь добавлено: ${_int(data['enqueued'])}. '
          'Пропущено: ${_int(data['skipped'])}. Ошибок: ${_int(data['failed'])}.',
        ),
        action: widget.onOpenDownloads == null
            ? null
            : SnackBarAction(label: 'Загрузки', onPressed: widget.onOpenDownloads!),
      ),
    );
  }

  Future<void> _openHistoryPlan(String id) async {
    await _run(() async {
      _plan = await widget.bridge.plan(id);
    });
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
            tooltip: 'Обновить',
            onPressed: _busy ? null : _refreshPlan,
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
                _controlsCard(),
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
                if (_plan == null)
                  const Card(
                    key: Key('sync-no-plan'),
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'Создайте план, чтобы увидеть dry-run изменений. До применения ничего не скачивается.',
                      ),
                    ),
                  )
                else ...[
                  _planStatusBanner(_plan!),
                  _summaryCard(_plan!),
                  const SizedBox(height: 12),
                  _planActions(_plan!),
                  const SizedBox(height: 12),
                  _details(_plan!),
                ],
                const SizedBox(height: 20),
                _historyCard(),
              ],
            ),
    );
  }

  Widget _controlsCard() {
    final selectedKey = _scopeType == 'all' ? 'all|' : '$_scopeType|${_scopeId ?? ''}';
    final values = _scopes.map((scope) {
      final type = '${scope['type'] ?? 'all'}';
      final id = '${scope['id'] ?? ''}';
      return DropdownMenuItem<String>(
        value: '$type|$id',
        child: Text('${scope['title'] ?? id}'),
      );
    }).toList();
    final configured = _target['targetConfigured'] == true;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Область синхронизации', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              key: const Key('sync-scope-selector'),
              initialValue: values.any((item) => item.value == selectedKey) ? selectedKey : (values.isEmpty ? null : values.first.value),
              items: values,
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value == null) return;
                      final parts = value.split('|');
                      setState(() {
                        _scopeType = parts.first;
                        _scopeId = parts.length > 1 && parts[1].isNotEmpty ? parts[1] : null;
                      });
                    },
              decoration: const InputDecoration(border: OutlineInputBorder()),
            ),
            const SizedBox(height: 16),
            Text('Download target', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              configured ? '${_target['targetPath']}' : 'Не выбран. План можно просмотреть, но Apply будет недоступен.',
              key: const Key('sync-target-state'),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  key: const Key('sync-select-target'),
                  onPressed: _busy ? null : _chooseTarget,
                  icon: const Icon(Icons.folder_open),
                  label: Text(configured ? 'Изменить папку' : 'Выбрать папку'),
                ),
                FilledButton.icon(
                  key: const Key('sync-create-plan'),
                  onPressed: _busy ? null : _createPlan,
                  icon: const Icon(Icons.fact_check_outlined),
                  label: const Text('Создать план'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _planStatusBanner(Map<String, dynamic> plan) {
    final status = '${plan['status'] ?? ''}';
    if (status == 'stale') {
      return Card(
        key: const Key('sync-stale-banner'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              const Icon(Icons.warning_amber),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Состояние библиотеки изменилось после создания плана. Создайте новый план перед применением.',
                ),
              ),
              FilledButton(
                onPressed: _busy ? null : _createPlan,
                child: const Text('Создать новый'),
              ),
            ],
          ),
        ),
      );
    }
    if (plan['legacy'] == true) {
      return const Card(
        key: Key('sync-legacy-banner'),
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('Legacy / unsupported plan. Он доступен только для просмотра и не может быть применён v0.8.'),
        ),
      );
    }
    if (status == 'applied' || status == 'partially_applied') {
      return Card(
        key: const Key('sync-apply-result'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(status == 'applied' ? 'План применён: безопасные операции обработаны.' : 'План применён частично: некоторые операции завершились ошибкой.'),
        ),
      );
    }
    return const SizedBox.shrink();
  }

  Widget _summaryCard(Map<String, dynamic> plan) {
    final summary = _summary(plan);
    Widget value(String label, String key) => SizedBox(
          width: 210,
          child: ListTile(
            dense: true,
            title: Text(label),
            trailing: Text('${_int(summary[key])}', style: const TextStyle(fontWeight: FontWeight.bold)),
          ),
        );
    return Card(
      key: const Key('sync-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Текущий план', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 4),
            Text('${plan['scopeLabel'] ?? plan['scopeType']} · ${plan['createdAt'] ?? ''}'),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                value('Desired', 'desiredTracks'),
                value('Covered', 'alreadyCovered'),
                value('Download', 'readyToDownload'),
                value('Already queued', 'alreadyQueued'),
                value('Decide', 'missingUndecided'),
                value('Ignored', 'ignoredMissing'),
                value('Identity review', 'identityReview'),
                value('Not analyzed', 'notAnalyzed'),
                value('Variant issues', 'variantIssues'),
              ],
            ),
            const Divider(),
            Text(
              'Current coverage: ${summary['currentCoveragePercent'] ?? 0}%   '
              'Projected after successful planned downloads: ${summary['projectedCoveragePercent'] ?? 0}%',
              key: const Key('sync-projected-coverage'),
            ),
            const SizedBox(height: 4),
            const Text('Projected — расчёт при условии успеха запланированных загрузок, а не гарантия.'),
          ],
        ),
      ),
    );
  }

  Widget _planActions(Map<String, dynamic> plan) {
    final status = '${plan['status'] ?? ''}';
    final targetOk = _target['targetConfigured'] == true;
    final canApply = !_busy && status == 'planned' && targetOk && plan['legacy'] != true;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          key: const Key('sync-apply'),
          onPressed: canApply ? _apply : null,
          icon: const Icon(Icons.playlist_add_check),
          label: const Text('Применить'),
        ),
        if (status == 'planned')
          OutlinedButton(
            key: const Key('sync-cancel-plan'),
            onPressed: _busy ? null : _cancelPlan,
            child: const Text('Отменить план'),
          ),
        if (widget.onOpenDownloads != null)
          TextButton.icon(
            key: const Key('sync-open-downloads'),
            onPressed: widget.onOpenDownloads,
            icon: const Icon(Icons.download_outlined),
            label: const Text('Открыть Загрузки'),
          ),
      ],
    );
  }

  Widget _details(Map<String, dynamic> plan) {
    final operations = _maps(plan['operations']);
    final downloads = operations.where((item) => item['type'] == 'enqueue_download').toList();
    final decisions = operations.where((item) => item['type'] == 'user_decision_required').toList();
    final identity = operations.where((item) => item['type'] == 'review_identity' && item['reason'] != 'matching_required').toList();
    final notAnalyzed = operations.where((item) => item['type'] == 'review_identity' && item['reason'] == 'matching_required').toList();
    final variants = operations.where((item) => item['type'] == 'review_variant').toList();
    final localOnly = operations.where((item) => item['type'] == 'local_only').toList();
    return Card(
      key: const Key('sync-plan-details'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            _group('К загрузке', downloads, _downloadRow),
            _group('Требует решения', decisions, _decisionRow),
            _group('Проверить сопоставление', identity, _identityRow),
            _group('Matching required', notAnalyzed, _identityRow),
            _group('Проблемы версии', variants, _variantRow),
            _group('Local only / Outside scope', localOnly, _infoRow),
          ],
        ),
      ),
    );
  }

  Widget _group(
    String title,
    List<Map<String, dynamic>> items,
    Widget Function(Map<String, dynamic>) row,
  ) {
    return ExpansionTile(
      key: Key('sync-group-$title'),
      initiallyExpanded: items.isNotEmpty && title == 'К загрузке',
      title: Text('$title (${items.length})'),
      children: items.isEmpty ? const [ListTile(title: Text('Нет элементов'))] : items.map(row).toList(),
    );
  }

  Widget _downloadRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    final status = '${item['status'] ?? ''}';
    return ListTile(
      key: Key('sync-download-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text('Missing · Wanted${status == 'skipped' ? ' · Already queued' : ''}'),
      trailing: const Icon(Icons.download_outlined),
    );
  }

  Widget _decisionRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    final id = '${item['externalId'] ?? ''}';
    return ListTile(
      key: Key('sync-decision-$id'),
      title: Text(_trackTitle(metadata)),
      subtitle: const Text('Missing · требуется решение'),
      trailing: Wrap(
        spacing: 4,
        children: [
          TextButton(onPressed: _busy ? null : () => _setAction(id, 'wanted'), child: const Text('Нужен')),
          TextButton(onPressed: _busy ? null : () => _setAction(id, 'ignored'), child: const Text('Игнорировать')),
        ],
      ),
    );
  }

  Widget _identityRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    return ListTile(
      key: Key('sync-review-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text(item['reason'] == 'matching_required' ? 'Matching required' : 'Needs Review'),
      trailing: widget.onOpenMatching == null
          ? null
          : TextButton(onPressed: widget.onOpenMatching, child: const Text('Открыть сопоставление')),
    );
  }

  Widget _variantRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    final variant = '${metadata['variantStatus'] ?? item['reason'] ?? ''}';
    return ListTile(
      key: Key('sync-variant-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text('Covered · $variant'),
      trailing: widget.onOpenMatching == null
          ? null
          : TextButton(onPressed: widget.onOpenMatching, child: const Text('Открыть проверку версии')),
    );
  }

  Widget _infoRow(Map<String, dynamic> item) {
    final metadata = _metadata(item);
    return ListTile(
      key: Key('sync-local-${item['externalId']}'),
      title: Text(_trackTitle(metadata)),
      subtitle: Text(item['reason'] == 'outside_selected_scope' ? 'Outside this scope' : 'Local only'),
    );
  }

  Widget _historyCard() {
    return Card(
      key: const Key('sync-history'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('История планов', style: Theme.of(context).textTheme.titleMedium),
            if (_history.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text('Сохранённых планов пока нет.'),
              )
            else
              ..._history.map(
                (item) => ListTile(
                  title: Text('${item['scopeLabel'] ?? item['scopeType']} · ${item['status']}'),
                  subtitle: Text('${item['createdAt']} · operations: ${item['operationCount'] ?? 0}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _openHistoryPlan('${item['id']}'),
                ),
              ),
          ],
        ),
      ),
    );
  }

  static Map<String, dynamic> _summary(Map<String, dynamic> plan) {
    final value = plan['summary'];
    return value is Map ? Map<String, dynamic>.from(value) : const {};
  }

  static Map<String, dynamic> _metadata(Map<String, dynamic> operation) {
    final value = operation['metadata'];
    return value is Map ? Map<String, dynamic>.from(value) : const {};
  }

  static String _trackTitle(Map<String, dynamic> metadata) {
    final rawArtists = metadata['artists'];
    final artists = rawArtists is List ? rawArtists.map((e) => '$e').where((e) => e.isNotEmpty).join(', ') : '';
    final title = '${metadata['title'] ?? ''}';
    return artists.isEmpty ? title : '$artists — $title';
  }

  static int _int(Object? value) => value is num ? value.toInt() : int.tryParse('$value') ?? 0;

  static List<Map<String, dynamic>> _maps(Object? value) => value is List
      ? value.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList()
      : <Map<String, dynamic>>[];

  static String _message(Object error) => error is SyncBridgeException ? error.message : error.toString();
}
