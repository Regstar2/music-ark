import 'dart:async';

import 'package:flutter/material.dart';

import 'desktop_file_actions.dart';
import 'download_bridge.dart';
import 'folder_picker.dart';

class DownloadPage extends StatefulWidget {
  const DownloadPage({
    super.key,
    required this.bridge,
    this.active = true,
    this.folderPicker = const SystemLocalFolderPicker(),
    this.fileActions = const SystemLocalFileActions(),
  });

  final DownloadBridgeClient bridge;
  final bool active;
  final LocalFolderPicker folderPicker;
  final LocalFileActions fileActions;

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
  bool _stopWorker = false;
  String? _error;
  Map<String, dynamic> _summary = const {};
  Map<String, dynamic> _settings = const {};
  List<Map<String, dynamic>> _items = const [];
  final Set<String> _visiblePaths = {};
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  @override
  void didUpdateWidget(covariant DownloadPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active && !widget.active) {
      // IndexedStack keeps this State alive off-screen. Never let a queue worker
      // silently drain old tasks after the user leaves Downloads.
      _stopWorker = true;
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  @override
  void dispose() {
    _stopWorker = true;
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
        final ids = _items.map((item) => '${item['id']}').toSet();
        _visiblePaths.removeWhere((id) => !ids.contains(id));
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

  List<String> _idsFromPayload(Map<String, dynamic> payload) {
    final raw = payload['items'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((item) => (item['id'] ?? '').toString().trim())
        .where((id) => id.isNotEmpty)
        .toList(growable: false);
  }

  Future<List<String>> _queuedTaskIds() async {
    final payload = await widget.bridge.tasks(status: 'queued', limit: 5000);
    return _idsFromPayload(payload);
  }

  Future<void> _enqueueWanted() async {
    if (_workerActive || !widget.active) return;
    if (!await _ensureTarget()) return;
    try {
      // Snapshot existing queue first. "Download all Wanted" may enqueue thousands
      // of new tasks, but it must never auto-run unrelated leftovers from old tests.
      final before = (await _queuedTaskIds()).toSet();
      final result = await widget.bridge.enqueueWanted();
      final created = (result['created'] as num?)?.toInt() ?? 0;
      final existing = (result['existing'] as num?)?.toInt() ?? 0;
      final after = await _queuedTaskIds();
      final newTaskIds = after.where((id) => !before.contains(id)).toList(growable: false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              newTaskIds.isEmpty && existing > 0
                  ? 'Новых загрузок нет. Старые задачи оставлены в очереди.'
                  : 'Добавлено в текущую загрузку: ${newTaskIds.length}',
            ),
          ),
        );
      }
      if (created > 0 && newTaskIds.isNotEmpty) {
        await _runQueue(skipTargetCheck: true, taskIds: newTaskIds);
      } else {
        await _load();
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _runQueue({
    bool skipTargetCheck = false,
    Iterable<String>? taskIds,
  }) async {
    if (_workerActive || !widget.active) return;
    if (!skipTargetCheck && !await _ensureTarget()) return;

    final ids = taskIds == null
        ? await _queuedTaskIds()
        : taskIds.map((id) => id.trim()).where((id) => id.isNotEmpty).toSet().toList();
    if (ids.isEmpty) {
      await _load();
      return;
    }

    setState(() {
      _workerActive = true;
      _stopWorker = false;
      _error = null;
    });
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(milliseconds: 800), (_) {
      if (widget.active && !_stopWorker) _load();
    });
    try {
      // Run one persisted task at a time. Unlike bridge.runQueue(), this gives the
      // UI a cancellation boundary between tracks and prevents an off-screen page
      // from draining thousands of stale queued tasks.
      for (final taskId in ids) {
        if (_stopWorker || !widget.active) break;
        try {
          await widget.bridge.runTask(taskId);
        } on DownloadBridgeException catch (error) {
          if (error.code == 'invalid_state') continue;
          if (error.code == 'worker_busy') {
            if (mounted) {
              setState(() => _error = 'Уже выполняется другая загрузка. Очередь остановлена.');
            }
            break;
          }
          rethrow;
        }
      }
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
    if (_workerActive || !widget.active) return;
    try {
      await widget.bridge.retry(taskId);
      // Retry means this task only. It must not wake unrelated queued work.
      await _runQueue(taskIds: [taskId]);
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

  Future<void> _cancelQueued() async {
    if (_workerActive) return;
    try {
      final ids = await _queuedTaskIds();
      if (!mounted) return;
      if (ids.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Очередь уже пуста.')),
        );
        return;
      }
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Отменить очередь?'),
          content: Text(
            'Будут отменены ${ids.length} ожидающих загрузок. Уже скачанные файлы не удаляются.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Назад'),
            ),
            FilledButton(
              key: const Key('downloads-cancel-queued-confirm'),
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Отменить очередь'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
      for (final id in ids) {
        await widget.bridge.cancel(id);
      }
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

  Future<void> _play(String path) async {
    try {
      await widget.fileActions.play(path);
    } catch (error) {
      if (mounted) setState(() => _error = 'Не удалось открыть трек: $error');
    }
  }

  Future<void> _reveal(String path) async {
    try {
      await widget.fileActions.reveal(path);
    } catch (error) {
      if (mounted) setState(() => _error = 'Не удалось открыть расположение файла: $error');
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
                    Card(
                      key: const Key('downloads-empty'),
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(
                          _filter.isEmpty
                              ? 'Активных загрузок нет.'
                              : 'Для выбранного фильтра загрузок нет.',
                        ),
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
          onPressed: _workerActive ? null : _chooseTarget,
          child: Text(configured ? 'Изменить' : 'Выбрать'),
        ),
      ),
    );
  }

  Widget _actions() {
    final queued = (_summary['queued'] as num?)?.toInt() ?? 0;
    return Wrap(
      spacing: 10,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          key: const Key('downloads-enqueue-wanted'),
          onPressed: _workerActive || !widget.active ? null : _enqueueWanted,
          icon: const Icon(Icons.download_for_offline_outlined),
          label: const Text('Скачать все «Нужные»'),
        ),
        FilledButton.tonalIcon(
          key: const Key('downloads-run'),
          onPressed: _workerActive || !widget.active ? null : _runQueue,
          icon: _workerActive
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.play_arrow),
          label: const Text('Продолжить очередь'),
        ),
        if (queued > 0)
          TextButton.icon(
            key: const Key('downloads-cancel-queued'),
            onPressed: _workerActive ? null : _cancelQueued,
            icon: const Icon(Icons.clear_all),
            label: Text('Отменить очередь ($queued)'),
          ),
        TextButton(
          key: const Key('downloads-clear-completed'),
          onPressed: _workerActive ? null : _clearCompleted,
          child: const Text('Очистить завершённые'),
        ),
      ],
    );
  }

  Widget _filterBar() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
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
    final id = '${task['id']}';
    final status = (task['status'] ?? '').toString();
    final progress = task['progress'];
    final progressValue = progress is num ? progress.toDouble().clamp(0.0, 1.0).toDouble() : null;
    final progressPercent = ((progressValue ?? 0.0) * 100).round();
    final artists = task['artists'] is List
        ? (task['artists'] as List).map((e) => e.toString()).join(', ')
        : '';
    final downloaded = (task['downloadedBytes'] as num?)?.toInt() ?? 0;
    final total = (task['totalBytes'] as num?)?.toInt();
    final path = (task['targetPath'] ?? '').toString();
    final showPath = _visiblePaths.contains(id);
    final completed = status == 'completed' && path.isNotEmpty;

    return Card(
      key: Key('download-task-$id'),
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
                key: Key('download-progress-$id'),
                value: progressValue,
              ),
              const SizedBox(height: 6),
              Text(total == null
                  ? '${_bytes(downloaded)} загружено'
                  : '${_bytes(downloaded)} / ${_bytes(total)} ($progressPercent%)'),
            ],
            if ((task['error'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('${task['error']}', style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            if (path.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  if (completed)
                    IconButton(
                      key: Key('download-play-$id'),
                      tooltip: 'Воспроизвести',
                      onPressed: () => _play(path),
                      icon: const Icon(Icons.play_arrow),
                    ),
                  if (completed)
                    IconButton(
                      key: Key('download-reveal-$id'),
                      tooltip: 'Открыть расположение файла',
                      onPressed: () => _reveal(path),
                      icon: const Icon(Icons.folder_open_outlined),
                    ),
                  TextButton.icon(
                    key: Key('download-toggle-path-$id'),
                    onPressed: () {
                      setState(() {
                        if (showPath) {
                          _visiblePaths.remove(id);
                        } else {
                          _visiblePaths.add(id);
                        }
                      });
                    },
                    icon: Icon(showPath ? Icons.visibility_off_outlined : Icons.visibility_outlined, size: 18),
                    label: Text(showPath ? 'Скрыть путь' : 'Показать путь'),
                  ),
                ],
              ),
              if (showPath)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: SelectableText(
                    path,
                    key: Key('download-path-$id'),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
            ],
            if (task['canRetry'] == true || task['canCancel'] == true) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  if (task['canRetry'] == true)
                    TextButton(
                      key: Key('download-retry-$id'),
                      onPressed: _workerActive ? null : () => _retry(id),
                      child: const Text('Повторить'),
                    ),
                  if (task['canCancel'] == true)
                    TextButton(
                      key: Key('download-cancel-$id'),
                      onPressed: () => _cancel(id),
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
