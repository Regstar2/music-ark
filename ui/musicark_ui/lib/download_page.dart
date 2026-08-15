import 'dart:async';

import 'package:flutter/material.dart';

import 'download_bridge.dart';
import 'folder_picker.dart';

class DownloadPage extends StatefulWidget {
  const DownloadPage({
    super.key,
    required this.bridge,
    this.folderPicker = const SystemLocalFolderPicker(),
  });

  final DownloadBridgeClient bridge;
  final LocalFolderPicker folderPicker;

  @override
  State<DownloadPage> createState() => _DownloadPageState();
}

class _DownloadPageState extends State<DownloadPage> {
  static const _filters = <String, String>{
    'Все': '',
    'В очереди': 'queued',
    'Загружаются': 'running',
    'Завершены': 'completed',
    'Ошибки': 'failed',
  };

  String _filter = '';
  bool _loading = true;
  bool _workerActive = false;
  String? _error;
  Map<String, dynamic> _summary = const {};
  Map<String, dynamic> _settings = const {};
  List<Map<String, dynamic>> _items = const [];
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _initialize() async {
    try {
      await widget.bridge.recover();
    } catch (_) {
      // Loading below surfaces any persistent bridge error. Recovery is best-effort.
    }
    await _load();
  }

  Future<void> _load({bool showSpinner = false}) async {
    if (showSpinner && mounted) setState(() => _loading = true);
    try {
      final results = await Future.wait([
        widget.bridge.summary(),
        widget.bridge.tasks(status: _filter),
      ]);
      if (!mounted) return;
      final taskPayload = results[1];
      final rawItems = taskPayload['items'];
      setState(() {
        _summary = Map<String, dynamic>.from(results[0]['counts'] as Map? ?? const {});
        _settings = Map<String, dynamic>.from(results[0]['settings'] as Map? ?? const {});
        _items = rawItems is List
            ? rawItems.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList()
            : <Map<String, dynamic>>[];
        _error = null;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  Future<bool> _ensureTarget() async {
    if (_settings['targetConfigured'] == true) return true;
    return _chooseTarget();
  }

  Future<bool> _chooseTarget() async {
    final path = await widget.folderPicker.pickDirectory();
    if (path == null || path.trim().isEmpty) return false;
    try {
      await widget.bridge.setTarget(path);
      await _load();
      return true;
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
      return false;
    }
  }

  Future<void> _enqueueWanted() async {
    if (!await _ensureTarget()) return;
    try {
      final result = await widget.bridge.enqueueWanted();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Добавлено в очередь: ${result['created'] ?? 0}')),
        );
      }
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _runQueue() async {
    if (_workerActive || !await _ensureTarget()) return;
    setState(() {
      _workerActive = true;
      _error = null;
    });
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(milliseconds: 800), (_) => _load());
    try {
      await widget.bridge.runQueue();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      _pollTimer?.cancel();
      _pollTimer = null;
      if (mounted) setState(() => _workerActive = false);
      await _load();
    }
  }

  Future<void> _retry(String taskId) async {
    try {
      await widget.bridge.retry(taskId);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _cancel(String taskId) async {
    try {
      await widget.bridge.cancel(taskId);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _clearCompleted() async {
    try {
      await widget.bridge.clearCompleted();
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Загрузки'),
        actions: [
          IconButton(
            key: const Key('downloads-refresh'),
            tooltip: 'Обновить',
            onPressed: () => _load(showSpinner: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                key: const Key('downloads-page'),
                padding: const EdgeInsets.all(20),
                children: [
                  _summaryCard(),
                  const SizedBox(height: 12),
                  _targetCard(),
                  const SizedBox(height: 12),
                  _actions(),
                  const SizedBox(height: 12),
                  _filterBar(),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    MaterialBanner(
                      key: const Key('downloads-error'),
                      content: Text(_error!),
                      actions: [
                        TextButton(
                          onPressed: () => setState(() => _error = null),
                          child: const Text('Скрыть'),
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 12),
                  if (_items.isEmpty)
                    const Card(
                      key: Key('downloads-empty'),
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text('Очередь пуста.'),
                      ),
                    )
                  else
                    ..._items.map(_taskCard),
                ],
              ),
            ),
    );
  }

  Widget _summaryCard() {
    int count(String key) => (_summary[key] as num?)?.toInt() ?? 0;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 24,
          runSpacing: 8,
          children: [
            Text('В очереди: ${count('queued')}'),
            Text('Загружается: ${count('running')}'),
            Text('Завершено: ${count('completed')}'),
            Text('Ошибки: ${count('failed')}'),
          ],
        ),
      ),
    );
  }

  Widget _targetCard() {
    final configured = _settings['targetConfigured'] == true;
    return Card(
      child: ListTile(
        leading: Icon(configured ? Icons.folder : Icons.folder_off_outlined),
        title: Text(configured ? 'Папка загрузок' : 'Выберите папку для загрузок'),
        subtitle: configured ? Text('${_settings['targetPath']}') : null,
        trailing: TextButton(
          key: const Key('downloads-select-target'),
          onPressed: _chooseTarget,
          child: Text(configured ? 'Изменить' : 'Выбрать'),
        ),
      ),
    );
  }

  Widget _actions() {
    return Wrap(
      spacing: 10,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          key: const Key('downloads-enqueue-wanted'),
          onPressed: _enqueueWanted,
          icon: const Icon(Icons.playlist_add),
          label: const Text('Добавить все «Нужные»'),
        ),
        FilledButton.tonalIcon(
          key: const Key('downloads-run'),
          onPressed: _workerActive ? null : _runQueue,
          icon: _workerActive
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.download),
          label: const Text('Запустить очередь'),
        ),
        TextButton(
          key: const Key('downloads-clear-completed'),
          onPressed: _clearCompleted,
          child: const Text('Очистить завершённые'),
        ),
      ],
    );
  }

  Widget _filterBar() {
    return Wrap(
      spacing: 8,
      children: _filters.entries.map((entry) {
        return ChoiceChip(
          label: Text(entry.key),
          selected: _filter == entry.value,
          onSelected: (_) {
            setState(() => _filter = entry.value);
            _load();
          },
        );
      }).toList(),
    );
  }

  Widget _taskCard(Map<String, dynamic> task) {
    final status = (task['status'] ?? '').toString();
    final progress = task['progress'];
    final artists = task['artists'] is List
        ? (task['artists'] as List).map((e) => e.toString()).join(', ')
        : '';
    final downloaded = (task['downloadedBytes'] as num?)?.toInt() ?? 0;
    final total = (task['totalBytes'] as num?)?.toInt();
    return Card(
      key: Key('download-task-${task['id']}'),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    artists.isEmpty ? '${task['title']}' : '$artists — ${task['title']}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Chip(label: Text(_statusLabel(status))),
              ],
            ),
            const SizedBox(height: 6),
            Text('${task['provider']} • ID ${task['externalId']}'),
            if (status == 'running') ...[
              const SizedBox(height: 10),
              LinearProgressIndicator(
                key: Key('download-progress-${task['id']}'),
                value: progress is num
                    ? progress.toDouble().clamp(0.0, 1.0).toDouble()
                    : null,
              ),
              const SizedBox(height: 6),
              Text(total == null
                  ? '${_bytes(downloaded)} загружено'
                  : '${_bytes(downloaded)} / ${_bytes(total)} (${((progress as num?)?.toDouble() ?? 0) * 100).round()}%)'),
            ],
            if ((task['targetPath'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 6),
              Text('Файл: ${task['targetPath']}', style: Theme.of(context).textTheme.bodySmall),
            ],
            if ((task['error'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('${task['error']}', style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            if (task['canRetry'] == true || task['canCancel'] == true) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  if (task['canRetry'] == true)
                    TextButton(
                      key: Key('download-retry-${task['id']}'),
                      onPressed: () => _retry('${task['id']}'),
                      child: const Text('Повторить'),
                    ),
                  if (task['canCancel'] == true)
                    TextButton(
                      key: Key('download-cancel-${task['id']}'),
                      onPressed: () => _cancel('${task['id']}'),
                      child: const Text('Отменить'),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _statusLabel(String status) => switch (status) {
        'queued' => 'В очереди',
        'running' => 'Загружается',
        'completed' => 'Завершено',
        'failed' => 'Ошибка',
        'needs_review' => 'Нужна проверка',
        'cancelled' => 'Отменено',
        'skipped' => 'Пропущено',
        _ => status,
      };

  String _bytes(int value) {
    if (value >= 1024 * 1024 * 1024) return '${(value / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
    if (value >= 1024 * 1024) return '${(value / (1024 * 1024)).toStringAsFixed(1)} MB';
    if (value >= 1024) return '${(value / 1024).toStringAsFixed(1)} KB';
    return '$value B';
  }
}
