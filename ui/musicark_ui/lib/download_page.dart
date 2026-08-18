import 'dart:async';

import 'package:flutter/material.dart';

import 'app_localizations_ext.dart';
import 'coverage_bridge.dart';
import 'desktop_file_actions.dart';
import 'download_bridge.dart';
import 'folder_picker.dart';

class DownloadPage extends StatefulWidget {
  const DownloadPage({
    super.key,
    required this.bridge,
    this.coverageBridge,
    this.active = true,
    this.folderPicker = const SystemLocalFolderPicker(),
    this.fileActions = const SystemLocalFileActions(),
  });

  final DownloadBridgeClient bridge;
  final CoverageBridgeClient? coverageBridge;
  final bool active;
  final LocalFolderPicker folderPicker;
  final LocalFileActions fileActions;

  @override
  State<DownloadPage> createState() => _DownloadPageState();
}

class _DownloadPageState extends State<DownloadPage> {
  final TextEditingController _search = TextEditingController();
  final Set<String> _visiblePaths = {};
  final Set<String> _wantedRunning = {};
  final Set<String> _selectedTasks = {};
  final Set<String> _selectedWanted = {};
  final Set<String> _busyTasks = {};

  String _filter = '';
  bool _wantedTab = false;
  bool _loading = true;
  bool _wantedLoading = false;
  bool _workerActive = false;
  bool _bulkBusy = false;
  bool _stopWorker = false;
  String? _error;
  Map<String, dynamic> _summary = const {};
  Map<String, dynamic> _settings = const {};
  List<Map<String, dynamic>> _items = const [];
  List<Map<String, dynamic>> _wantedItems = const [];
  int _wantedTotal = 0;
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
      _stopWorker = true;
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  @override
  void dispose() {
    _stopWorker = true;
    _pollTimer?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _initialize() async {
    try {
      await widget.bridge.recover();
    } catch (_) {
      // Loading below surfaces persistent bridge errors. Recovery remains best-effort.
    }
    await _load();
  }

  Future<void> _load({bool showSpinner = false}) async {
    if (showSpinner && mounted) setState(() => _loading = true);
    try {
      final taskStatus = _filter == 'failed' ? '' : _filter;
      final results = await Future.wait([
        widget.bridge.summary(),
        widget.bridge.tasks(status: taskStatus, limit: 5000),
      ]);
      if (!mounted) return;
      final rawItems = results[1]['items'];
      var items = rawItems is List
          ? rawItems.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList()
          : <Map<String, dynamic>>[];
      if (_filter == 'failed') {
        items = items
            .where((item) => item['status'] == 'failed' || item['status'] == 'needs_review')
            .toList(growable: false);
      }
      final ids = items.map((item) => '${item['id']}').toSet();
      setState(() {
        _summary = Map<String, dynamic>.from(results[0]['counts'] as Map? ?? const {});
        _settings = Map<String, dynamic>.from(results[0]['settings'] as Map? ?? const {});
        _items = items;
        _visiblePaths.removeWhere((id) => !ids.contains(id));
        _selectedTasks.removeWhere((id) => !ids.contains(id));
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

  Future<void> _loadWanted({bool showSpinner = false}) async {
    final bridge = widget.coverageBridge;
    if (bridge == null) {
      if (mounted) {
        setState(() {
          _wantedItems = const [];
          _wantedTotal = 0;
          _selectedWanted.clear();
          _wantedLoading = false;
        });
      }
      return;
    }
    if (showSpinner && mounted) setState(() => _wantedLoading = true);
    try {
      final payload = await bridge.coverageTracks(
        limit: 1000,
        offset: 0,
        status: 'missing',
        userAction: 'wanted',
        sort: 'artist',
      );
      if (!mounted) return;
      final rawItems = payload['items'];
      final items = rawItems is List
          ? rawItems.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList()
          : <Map<String, dynamic>>[];
      final ids = items.map((item) => '${item['externalId']}').toSet();
      setState(() {
        _wantedItems = items;
        _wantedTotal = int.tryParse('${payload['count'] ?? items.length}') ?? items.length;
        _selectedWanted.removeWhere((id) => !ids.contains(id));
        _wantedLoading = false;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _wantedLoading = false;
        _error = error.toString();
      });
    }
  }

  Future<void> _refreshCurrent({bool showSpinner = false}) async {
    if (_wantedTab) {
      await _loadWanted(showSpinner: showSpinner);
    } else {
      await _load(showSpinner: showSpinner);
    }
  }

  void _selectTab(bool wanted) {
    if (_wantedTab == wanted) return;
    setState(() {
      _wantedTab = wanted;
      _error = null;
      _search.clear();
      _selectedTasks.clear();
      _selectedWanted.clear();
      if (wanted) _wantedLoading = true;
    });
    wanted ? _loadWanted() : _load();
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
      if (_wantedTab) await _loadWanted();
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

  List<Map<String, dynamic>> get _visibleTaskItems {
    final query = _search.text.trim().toLowerCase();
    if (query.isEmpty) return _items;
    return _items.where((task) {
      final artists = task['artists'] is List ? (task['artists'] as List).join(' ') : '';
      final haystack = [
        task['title'],
        artists,
        task['album'],
        task['provider'],
        task['externalId'],
        task['id'],
      ].where((value) => value != null).join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList(growable: false);
  }

  List<Map<String, dynamic>> get _visibleWantedItems {
    final query = _search.text.trim().toLowerCase();
    if (query.isEmpty) return _wantedItems;
    return _wantedItems.where((item) {
      final provider = item['provider'] is Map
          ? Map<String, dynamic>.from(item['provider'] as Map)
          : const <String, dynamic>{};
      final artists = provider['artists'] is List ? (provider['artists'] as List).join(' ') : '';
      final haystack = [
        provider['title'],
        artists,
        provider['album_title'],
        provider['album'],
        item['providerId'],
        item['externalId'],
      ].where((value) => value != null).join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList(growable: false);
  }

  Future<void> _enqueueWanted() async {
    if (_workerActive || _bulkBusy || !widget.active) return;
    if (!await _ensureTarget()) return;
    setState(() => _bulkBusy = true);
    try {
      final before = (await _queuedTaskIds()).toSet();
      final result = await widget.bridge.enqueueWanted();
      final created = (result['created'] as num?)?.toInt() ?? 0;
      final existing = (result['existing'] as num?)?.toInt() ?? 0;
      final after = await _queuedTaskIds();
      final newTaskIds = after.where((id) => !before.contains(id)).toList(growable: false);
      if (mounted) {
        final message = newTaskIds.isEmpty && existing > 0
            ? context.l10n.downloadsNoNewTasks
            : context.l10n.downloadsAddedTasks(newTaskIds.length);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      }
      if (created > 0 && newTaskIds.isNotEmpty) {
        await widget.bridge.runTasks(newTaskIds);
      }
      await _load();
      if (_wantedTab) await _loadWanted();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _bulkBusy = false);
    }
  }

  Future<void> _enqueueSingleWanted(String externalId) async {
    if (_workerActive || _bulkBusy || _wantedRunning.contains(externalId) || !widget.active) return;
    if (!await _ensureTarget()) return;
    setState(() {
      _wantedRunning.add(externalId);
      _error = null;
    });
    try {
      final queued = await widget.bridge.enqueue(externalId);
      final rawTask = queued['task'];
      final task = rawTask is Map ? Map<String, dynamic>.from(rawTask) : const <String, dynamic>{};
      final taskId = (task['id'] ?? '').toString();
      if ((task['status'] ?? '').toString() == 'queued' && taskId.isNotEmpty) {
        await widget.bridge.runTask(taskId);
      }
      await _load();
      await _loadWanted();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _wantedRunning.remove(externalId));
    }
  }

  Future<void> _downloadSelectedWanted() async {
    final ids = _selectedWanted.toList(growable: false);
    if (ids.isEmpty || _workerActive || _bulkBusy || !widget.active) return;
    if (!await _ensureTarget()) return;
    setState(() => _bulkBusy = true);
    try {
      final enqueued = await widget.bridge.enqueueSelected(ids);
      final taskIds = _idsFromPayload(enqueued)
          .where((id) => id.isNotEmpty)
          .toList(growable: false);
      if (taskIds.isNotEmpty) await widget.bridge.runTasks(taskIds);
      if (mounted) _showBatchResult(enqueued);
      await _load();
      await _loadWanted();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() {
          _bulkBusy = false;
          _selectedWanted.clear();
        });
      }
    }
  }

  Future<void> _runQueue({Iterable<String>? taskIds}) async {
    if (_workerActive || _bulkBusy || !widget.active) return;
    if (!await _ensureTarget()) return;
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
      for (final taskId in ids) {
        if (_stopWorker || !widget.active) break;
        try {
          await widget.bridge.runTask(taskId);
        } on DownloadBridgeException catch (error) {
          if (error.code == 'invalid_state') continue;
          if (error.code == 'worker_busy') {
            if (mounted) setState(() => _error = context.l10n.downloadsWorkerBusy);
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
      if (_wantedTab) await _loadWanted();
    }
  }

  Future<void> _retry(String taskId) async {
    if (_workerActive || _bulkBusy || !widget.active) return;
    setState(() => _busyTasks.add(taskId));
    try {
      await widget.bridge.retry(taskId);
      await _runQueue(taskIds: [taskId]);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busyTasks.remove(taskId));
    }
  }

  Future<void> _bulkRetry() async {
    final ids = _selectedForStatuses({'failed', 'needs_review'});
    if (ids.isEmpty || _workerActive || _bulkBusy || !widget.active) return;
    setState(() => _bulkBusy = true);
    try {
      final retried = await widget.bridge.retryTasks(ids);
      final runnable = (retried['items'] as List? ?? const [])
          .whereType<Map>()
          .where((item) => item['status'] == 'queued')
          .map((item) => '${item['id']}')
          .where((id) => id.isNotEmpty)
          .toList(growable: false);
      if (runnable.isNotEmpty) await widget.bridge.runTasks(runnable);
      if (mounted) _showBatchResult(retried);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() {
          _bulkBusy = false;
          _selectedTasks.clear();
        });
      }
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

  Future<void> _bulkCancel() async {
    final ids = _selectedForStatuses({'queued', 'running'});
    if (ids.isEmpty || _bulkBusy) return;
    final confirmed = await _confirm(
      title: context.l10n.downloadsCancelSelectedTitle,
      body: context.l10n.downloadsCancelSelectedBody(ids.length),
      confirmLabel: context.l10n.downloadsCancelSelectedConfirm(ids.length),
      confirmKey: const Key('downloads-bulk-cancel-confirm'),
    );
    if (!confirmed) return;
    setState(() => _bulkBusy = true);
    try {
      final result = await widget.bridge.cancelTasks(ids);
      if (mounted) _showBatchResult(result);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() {
          _bulkBusy = false;
          _selectedTasks.clear();
        });
      }
    }
  }

  Future<void> _removeOne(String taskId) async {
    final confirmed = await _confirm(
      title: context.l10n.downloadsRemoveTitle,
      body: context.l10n.downloadsRemoveBody,
      confirmLabel: context.l10n.downloadsRemove,
      confirmKey: Key('download-remove-confirm-$taskId'),
      destructive: true,
    );
    if (!confirmed) return;
    setState(() => _busyTasks.add(taskId));
    try {
      final result = await widget.bridge.removeTasks([taskId]);
      if (mounted) _showBatchResult(result);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busyTasks.remove(taskId));
    }
  }

  Future<void> _bulkRemove() async {
    final ids = _selectedForStatuses({'failed', 'needs_review'});
    if (ids.isEmpty || _bulkBusy) return;
    final confirmed = await _confirm(
      title: context.l10n.downloadsRemoveSelectedTitle(ids.length),
      body: context.l10n.downloadsRemoveSelectedBody,
      confirmLabel: context.l10n.downloadsRemoveSelectedConfirm(ids.length),
      confirmKey: const Key('downloads-bulk-remove-confirm'),
      destructive: true,
    );
    if (!confirmed) return;
    setState(() => _bulkBusy = true);
    try {
      final result = await widget.bridge.removeTasks(ids);
      if (mounted) _showBatchResult(result);
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() {
          _bulkBusy = false;
          _selectedTasks.clear();
        });
      }
    }
  }

  List<String> _selectedForStatuses(Set<String> statuses) {
    return _items
        .where((item) => _selectedTasks.contains('${item['id']}') && statuses.contains('${item['status']}'))
        .map((item) => '${item['id']}')
        .toList(growable: false);
  }

  Future<void> _cancelQueued() async {
    if (_workerActive || _bulkBusy) return;
    try {
      final ids = await _queuedTaskIds();
      if (!mounted) return;
      if (ids.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(context.l10n.downloadsQueueEmpty)),
        );
        return;
      }
      final confirmed = await _confirm(
        title: context.l10n.downloadsCancelQueueTitle,
        body: context.l10n.downloadsCancelQueueBody(ids.length),
        confirmLabel: context.l10n.downloadsCancelQueue,
        confirmKey: const Key('downloads-cancel-queued-confirm'),
      );
      if (!confirmed) return;
      await widget.bridge.cancelTasks(ids);
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
      if (mounted) setState(() => _error = context.l10n.localPlayFailed('$error'));
    }
  }

  Future<void> _reveal(String path) async {
    try {
      await widget.fileActions.reveal(path);
    } catch (error) {
      if (mounted) setState(() => _error = context.l10n.localRevealFailed('$error'));
    }
  }

  Future<bool> _confirm({
    required String title,
    required String body,
    required String confirmLabel,
    required Key confirmKey,
    bool destructive = false,
  }) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(context.l10n.cancel),
          ),
          FilledButton(
            key: confirmKey,
            style: destructive
                ? FilledButton.styleFrom(
                    backgroundColor: Theme.of(context).colorScheme.error,
                    foregroundColor: Theme.of(context).colorScheme.onError,
                  )
                : null,
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
    return confirmed == true;
  }

  void _showBatchResult(Map<String, dynamic> result) {
    final requested = (result['requested'] as num?)?.toInt() ?? 0;
    final succeeded = (result['succeeded'] as num?)?.toInt() ?? 0;
    final failed = (result['failed'] as num?)?.toInt() ?? 0;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(context.l10n.downloadsBatchResult(succeeded, requested, failed))),
    );
  }

  void _showDetails(Map<String, dynamic> task) {
    final id = '${task['id']}';
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(context.l10n.technicalDetails),
        content: SizedBox(
          width: 560,
          child: SelectableText(
            [
              'taskId: $id',
              'provider: ${task['provider'] ?? ''}',
              'externalId: ${task['externalId'] ?? ''}',
              'errorCode: ${task['errorCode'] ?? ''}',
              'message: ${task['error'] ?? ''}',
            ].join('\n'),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(context.l10n.close),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final busy = _wantedTab ? _wantedLoading : _loading;
    return Scaffold(
      appBar: AppBar(
        title: Text(context.l10n.downloadsTitle),
        actions: [
          IconButton(
            key: const Key('downloads-refresh'),
            tooltip: context.l10n.refresh,
            onPressed: () => _refreshCurrent(showSpinner: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: busy
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshCurrent,
              child: CustomScrollView(
                key: const Key('downloads-page'),
                slivers: [
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                    sliver: SliverToBoxAdapter(child: _pageHeader()),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    sliver: SliverToBoxAdapter(child: _tabs()),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                    sliver: SliverToBoxAdapter(
                      child: _wantedTab ? _wantedHeader() : _downloadsHeader(),
                    ),
                  ),
                  if (_error != null)
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
                      sliver: SliverToBoxAdapter(child: _errorBanner()),
                    ),
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                    sliver: _wantedTab ? _wantedListSliver() : _taskListSliver(),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _pageHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(context.l10n.downloadsSubtitle, style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 12),
      ],
    );
  }

  Widget _tabs() {
    final taskCount = (_summary['total'] as num?)?.toInt() ?? 0;
    return Align(
      alignment: Alignment.centerLeft,
      child: SegmentedButton<String>(
        key: const Key('downloads-tabs'),
        showSelectedIcon: false,
        segments: [
          ButtonSegment(
            value: 'tasks',
            label: Text(context.l10n.downloadsTabTasks(taskCount)),
            icon: const Icon(Icons.download_outlined),
          ),
          ButtonSegment(
            value: 'wanted',
            label: Text(context.l10n.downloadsTabWanted(_wantedTotal)),
            icon: const Icon(Icons.bookmark_outline),
          ),
        ],
        selected: {_wantedTab ? 'wanted' : 'tasks'},
        onSelectionChanged: (value) {
          if (value.isNotEmpty) _selectTab(value.first == 'wanted');
        },
      ),
    );
  }

  Widget _downloadsHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _summaryCards(),
        const SizedBox(height: 12),
        _targetCard(),
        const SizedBox(height: 12),
        _toolbar(),
        if (_selectedTasks.isNotEmpty) ...[
          const SizedBox(height: 10),
          _taskBulkBar(),
        ],
        const SizedBox(height: 14),
        Row(
          children: [
            Text(context.l10n.downloadsTasksTitle, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(width: 8),
            Text('${_visibleTaskItems.length}', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ],
    );
  }

  Widget _wantedHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _targetCard(),
        const SizedBox(height: 12),
        Card(
          key: const Key('downloads-wanted-summary'),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Wrap(
              spacing: 12,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(context.l10n.downloadsWantedCount(_wantedTotal)),
                FilledButton.icon(
                  key: const Key('downloads-wanted-download-all'),
                  onPressed: _workerActive || _bulkBusy || _wantedTotal == 0 ? null : _enqueueWanted,
                  icon: const Icon(Icons.download_for_offline_outlined),
                  label: Text(context.l10n.downloadsDownloadAll),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        _searchField(),
        const SizedBox(height: 10),
        _selectionToggle(
          selected: _selectedWanted,
          visibleIds: _visibleWantedItems.map((item) => '${item['externalId']}').toList(),
          onChanged: (ids) => setState(() {
            _selectedWanted
              ..clear()
              ..addAll(ids);
          }),
        ),
        if (_selectedWanted.isNotEmpty) ...[
          const SizedBox(height: 10),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Wrap(
                spacing: 10,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(context.l10n.downloadsSelected(_selectedWanted.length)),
                  FilledButton.icon(
                    key: const Key('downloads-wanted-download-selected'),
                    onPressed: _bulkBusy ? null : _downloadSelectedWanted,
                    icon: const Icon(Icons.download_outlined),
                    label: Text(context.l10n.downloadsDownloadSelected(_selectedWanted.length)),
                  ),
                  TextButton(
                    onPressed: () => setState(_selectedWanted.clear),
                    child: Text(context.l10n.downloadsClearSelection),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _summaryCards() {
    int count(String key) => (_summary[key] as num?)?.toInt() ?? 0;
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: [
        _summaryMetric(context.l10n.downloadsSummaryQueued, count('queued')),
        _summaryMetric(context.l10n.downloadsSummaryRunning, count('running')),
        _summaryMetric(context.l10n.downloadsSummaryCompleted, count('completed')),
        _summaryMetric(
          context.l10n.downloadsSummaryErrors,
          count('failed'),
          valueColor: Theme.of(context).colorScheme.error,
        ),
      ],
    );
  }

  Widget _summaryMetric(String label, int value, {Color? valueColor}) {
    return SizedBox(
      width: 180,
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 4),
              Text(
                '$value',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: valueColor),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _targetCard() {
    final configured = _settings['targetConfigured'] == true;
    return Card(
      child: ListTile(
        dense: true,
        leading: Icon(configured ? Icons.folder : Icons.folder_off_outlined),
        title: Text(
          configured ? context.l10n.downloadsTargetFolder : context.l10n.downloadsTargetChoose,
        ),
        subtitle: configured ? Text('${_settings['targetPath']}') : null,
        trailing: TextButton(
          key: const Key('downloads-select-target'),
          onPressed: _workerActive || _bulkBusy ? null : _chooseTarget,
          child: Text(configured ? context.l10n.downloadsChange : context.l10n.downloadsChoose),
        ),
      ),
    );
  }

  Widget _toolbar() {
    final queued = (_summary['queued'] as num?)?.toInt() ?? 0;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        _searchField(),
        ..._filterEntries().map((entry) {
          return ChoiceChip(
            key: Key('downloads-filter-${entry.$1.isEmpty ? 'all' : entry.$1}'),
            label: Text(entry.$2),
            selected: _filter == entry.$1,
            onSelected: (_) {
              setState(() {
                _filter = entry.$1;
                _selectedTasks.clear();
              });
              _load();
            },
          );
        }),
        FilledButton.tonalIcon(
          key: const Key('downloads-run'),
          onPressed: _workerActive || _bulkBusy || !widget.active ? null : _runQueue,
          icon: _workerActive
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.play_arrow),
          label: Text(context.l10n.downloadsContinueQueue),
        ),
        FilledButton.icon(
          key: const Key('downloads-enqueue-wanted'),
          onPressed: _workerActive || _bulkBusy || !widget.active ? null : _enqueueWanted,
          icon: const Icon(Icons.download_for_offline_outlined),
          label: Text(context.l10n.downloadsDownloadWanted),
        ),
        if (queued > 0)
          TextButton.icon(
            key: const Key('downloads-cancel-queued'),
            onPressed: _workerActive || _bulkBusy ? null : _cancelQueued,
            icon: const Icon(Icons.clear_all),
            label: Text(context.l10n.downloadsCancelQueueCount(queued)),
          ),
        TextButton(
          key: const Key('downloads-clear-completed'),
          onPressed: _workerActive || _bulkBusy ? null : _clearCompleted,
          child: Text(context.l10n.downloadsClearCompleted),
        ),
      ],
    );
  }

  Widget _searchField() {
    return SizedBox(
      width: 310,
      child: TextField(
        key: const Key('downloads-search'),
        controller: _search,
        decoration: InputDecoration(
          isDense: true,
          prefixIcon: const Icon(Icons.search),
          hintText: context.l10n.downloadsSearchHint,
          border: const OutlineInputBorder(),
        ),
        onChanged: (_) => setState(() {
          _selectedTasks.clear();
          _selectedWanted.clear();
        }),
      ),
    );
  }

  List<(String, String)> _filterEntries() => [
        ('', context.l10n.downloadsFilterAll),
        ('queued', context.l10n.downloadsFilterQueued),
        ('running', context.l10n.downloadsFilterRunning),
        ('completed', context.l10n.downloadsFilterCompleted),
        ('failed', context.l10n.downloadsFilterErrors),
      ];

  Widget _taskBulkBar() {
    final retry = _selectedForStatuses({'failed', 'needs_review'}).length;
    final cancel = _selectedForStatuses({'queued', 'running'}).length;
    return Card(
      key: const Key('downloads-bulk-bar'),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Wrap(
          spacing: 10,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(context.l10n.downloadsSelected(_selectedTasks.length)),
            if (retry > 0)
              FilledButton.tonal(
                key: const Key('downloads-bulk-retry'),
                onPressed: _bulkBusy ? null : _bulkRetry,
                child: Text(context.l10n.downloadsBulkRetry(retry)),
              ),
            if (cancel > 0)
              FilledButton.tonal(
                key: const Key('downloads-bulk-cancel'),
                onPressed: _bulkBusy ? null : _bulkCancel,
                child: Text(context.l10n.downloadsBulkCancel(cancel)),
              ),
            if (retry > 0)
              TextButton(
                key: const Key('downloads-bulk-remove'),
                onPressed: _bulkBusy ? null : _bulkRemove,
                child: Text(
                  context.l10n.downloadsBulkRemove(retry),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            TextButton(
              onPressed: () => setState(_selectedTasks.clear),
              child: Text(context.l10n.downloadsClearSelection),
            ),
          ],
        ),
      ),
    );
  }

  Widget _selectionToggle({
    required Set<String> selected,
    required List<String> visibleIds,
    required ValueChanged<Set<String>> onChanged,
  }) {
    final visible = visibleIds.toSet();
    final allSelected = visible.isNotEmpty && visible.every(selected.contains);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Checkbox(
          key: ValueKey(_wantedTab ? 'downloads-wanted-select-all' : 'downloads-select-all'),
          value: allSelected,
          onChanged: visible.isEmpty
              ? null
              : (value) {
                  final next = Set<String>.from(selected);
                  if (value == true) {
                    next.addAll(visible);
                  } else {
                    next.removeAll(visible);
                  }
                  onChanged(next);
                },
        ),
        Text(context.l10n.downloadsSelectAllVisible),
      ],
    );
  }

  Widget _errorBanner() {
    return MaterialBanner(
      key: const Key('downloads-error'),
      content: Text(_error!),
      actions: [
        TextButton(
          onPressed: () => setState(() => _error = null),
          child: Text(context.l10n.close),
        ),
      ],
    );
  }

  Widget _taskListSliver() {
    final items = _visibleTaskItems;
    if (items.isEmpty) {
      return SliverToBoxAdapter(
        child: Card(
          key: const Key('downloads-empty'),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              _search.text.trim().isEmpty
                  ? context.l10n.downloadsEmpty
                  : context.l10n.downloadsEmptyFiltered,
            ),
          ),
        ),
      );
    }
    return SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, index) => _taskRow(items[index]),
        childCount: items.length,
      ),
    );
  }

  Widget _wantedListSliver() {
    final items = _visibleWantedItems;
    if (items.isEmpty) {
      return SliverToBoxAdapter(
        child: Card(
          key: const Key('downloads-wanted-empty'),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              _search.text.trim().isEmpty
                  ? context.l10n.downloadsWantedEmpty
                  : context.l10n.downloadsEmptyFiltered,
            ),
          ),
        ),
      );
    }
    return SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, index) => _wantedRow(items[index]),
        childCount: items.length,
      ),
    );
  }

  Widget _taskRow(Map<String, dynamic> task) {
    final id = '${task['id']}';
    final status = '${task['status'] ?? ''}';
    final artists = task['artists'] is List ? (task['artists'] as List).map((e) => '$e').join(', ') : '';
    final title = '${task['title'] ?? task['externalId'] ?? id}';
    final progress = task['progress'];
    final progressValue = progress is num ? progress.toDouble().clamp(0.0, 1.0).toDouble() : null;
    final progressPercent = ((progressValue ?? 0.0) * 100).round();
    final downloaded = (task['downloadedBytes'] as num?)?.toInt() ?? 0;
    final total = (task['totalBytes'] as num?)?.toInt();
    final path = '${task['targetPath'] ?? ''}';
    final showPath = _visiblePaths.contains(id);
    final completed = status == 'completed' && path.isNotEmpty;
    final removable = status == 'failed' || status == 'needs_review';
    final busy = _busyTasks.contains(id);

    return Card(
      key: Key('download-task-$id'),
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Checkbox(
              key: Key('download-select-$id'),
              value: _selectedTasks.contains(id),
              onChanged: (value) => setState(() {
                value == true ? _selectedTasks.add(id) : _selectedTasks.remove(id);
              }),
            ),
            _artworkPlaceholder(title),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Tooltip(
                    message: artists.isEmpty ? title : '$artists — $title',
                    child: Text(
                      artists.isEmpty ? title : '$artists — $title',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    '${task['provider'] ?? ''} • ID ${task['externalId'] ?? ''}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  if (status == 'running') ...[
                    const SizedBox(height: 8),
                    LinearProgressIndicator(key: Key('download-progress-$id'), value: progressValue),
                    const SizedBox(height: 4),
                    Text(
                      total == null
                          ? context.l10n.downloadsDownloaded(_bytes(downloaded))
                          : context.l10n.downloadsProgress(
                              _bytes(downloaded),
                              _bytes(total),
                              progressPercent,
                            ),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  if ((task['error'] ?? '').toString().isNotEmpty) ...[
                    const SizedBox(height: 7),
                    Text(
                      _friendlyError('${task['errorCode'] ?? ''}'),
                      key: Key('download-friendly-error-$id'),
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ],
                  if (showPath && path.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: SelectableText(path, key: Key('download-path-$id')),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 310),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Chip(label: Text(_statusLabel(status))),
                  const SizedBox(height: 4),
                  Wrap(
                    alignment: WrapAlignment.end,
                    spacing: 4,
                    runSpacing: 4,
                    children: [
                      if (completed)
                        IconButton(
                          key: Key('download-play-$id'),
                          tooltip: context.l10n.play,
                          onPressed: () => _play(path),
                          icon: const Icon(Icons.play_arrow),
                        ),
                      if (completed)
                        IconButton(
                          key: Key('download-reveal-$id'),
                          tooltip: context.l10n.localRevealFile,
                          onPressed: () => _reveal(path),
                          icon: const Icon(Icons.folder_open_outlined),
                        ),
                      if (path.isNotEmpty)
                        TextButton.icon(
                          key: Key('download-toggle-path-$id'),
                          onPressed: () => setState(() {
                            showPath ? _visiblePaths.remove(id) : _visiblePaths.add(id);
                          }),
                          icon: Icon(showPath ? Icons.visibility_off_outlined : Icons.visibility_outlined, size: 18),
                          label: Text(
                            showPath ? context.l10n.downloadsHidePath : context.l10n.downloadsShowPath,
                          ),
                        ),
                      if (task['canRetry'] == true)
                        TextButton(
                          key: Key('download-retry-$id'),
                          onPressed: _workerActive || _bulkBusy || busy ? null : () => _retry(id),
                          child: Text(busy ? context.l10n.downloadsRetrying : context.l10n.downloadsRetry),
                        ),
                      if (task['canCancel'] == true)
                        TextButton(
                          key: Key('download-cancel-$id'),
                          onPressed: _bulkBusy ? null : () => _cancel(id),
                          child: Text(context.l10n.downloadsCancel),
                        ),
                      if (removable)
                        TextButton(
                          key: Key('download-remove-$id'),
                          onPressed: _bulkBusy || busy ? null : () => _removeOne(id),
                          child: Text(
                            context.l10n.downloadsRemove,
                            style: TextStyle(color: Theme.of(context).colorScheme.error),
                          ),
                        ),
                      if ((task['error'] ?? '').toString().isNotEmpty)
                        TextButton(
                          key: Key('download-details-$id'),
                          onPressed: () => _showDetails(task),
                          child: Text(context.l10n.downloadsDetails),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _wantedRow(Map<String, dynamic> item) {
    final id = '${item['externalId'] ?? ''}';
    final provider = item['provider'] is Map
        ? Map<String, dynamic>.from(item['provider'] as Map)
        : const <String, dynamic>{};
    final artists = provider['artists'] is List
        ? (provider['artists'] as List).map((e) => '$e').where((value) => value.isNotEmpty).join(', ')
        : '';
    final title = '${provider['title'] ?? id}';
    final album = '${provider['album_title'] ?? provider['album'] ?? ''}';
    final running = _wantedRunning.contains(id);
    return Card(
      key: ValueKey('downloads-wanted-$id'),
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        child: Row(
          children: [
            Checkbox(
              key: ValueKey('downloads-wanted-select-$id'),
              value: _selectedWanted.contains(id),
              onChanged: (value) => setState(() {
                value == true ? _selectedWanted.add(id) : _selectedWanted.remove(id);
              }),
            ),
            _artworkPlaceholder(title),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    artists.isEmpty ? title : '$artists — $title',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    [
                      if (album.isNotEmpty) album,
                      context.l10n.accountProvider,
                      'ID $id',
                    ].join(' • '),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 5),
                  Text(
                    context.l10n.downloadsNoLocalCopy,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            FilledButton.icon(
              key: ValueKey('downloads-wanted-download-$id'),
              onPressed: _workerActive || _bulkBusy || running ? null : () => _enqueueSingleWanted(id),
              icon: running
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.download, size: 18),
              label: Text(running ? context.l10n.downloadsDownloading : context.l10n.downloadsDownload),
            ),
          ],
        ),
      ),
    );
  }

  Widget _artworkPlaceholder(String title) {
    return Container(
      width: 52,
      height: 52,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(10),
      ),
      alignment: Alignment.center,
      child: const Icon(Icons.music_note_outlined),
    );
  }

  String _friendlyError(String code) => switch (code) {
        'authentication' => context.l10n.downloadsErrorAuthentication,
        'track_unavailable' || 'no_download_info' => context.l10n.downloadsErrorUnavailable,
        'network_error' || 'provider_request' => context.l10n.downloadsErrorProvider,
        'interrupted' => context.l10n.downloadsErrorInterrupted,
        'duration_mismatch' || 'coverage_not_updated' => context.l10n.downloadsErrorReview,
        'invalid_audio' => context.l10n.downloadsErrorInvalidAudio,
        _ => context.l10n.downloadsErrorGeneric,
      };

  String _statusLabel(String status) => switch (status) {
        'queued' => context.l10n.downloadsStatusQueued,
        'running' => context.l10n.downloadsStatusRunning,
        'completed' => context.l10n.downloadsStatusCompleted,
        'failed' => context.l10n.downloadsStatusFailed,
        'needs_review' => context.l10n.downloadsStatusReview,
        'cancelled' => context.l10n.downloadsStatusCancelled,
        'skipped' => context.l10n.downloadsStatusSkipped,
        _ => status,
      };

  String _bytes(int value) {
    if (value >= 1024 * 1024 * 1024) return '${(value / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
    if (value >= 1024 * 1024) return '${(value / (1024 * 1024)).toStringAsFixed(1)} MB';
    if (value >= 1024) return '${(value / 1024).toStringAsFixed(1)} KB';
    return '$value B';
  }
}
