import 'dart:convert';
import 'dart:io';

abstract interface class DownloadBridgeClient {
  Future<Map<String, dynamic>> summary();
  Future<Map<String, dynamic>> tasks({String status = '', int limit = 1000});
  Future<Map<String, dynamic>> enqueue(String externalId);
  Future<Map<String, dynamic>> enqueueWanted();
  Future<Map<String, dynamic>> enqueueSelected(List<String> externalIds);
  Future<Map<String, dynamic>> runQueue();
  Future<Map<String, dynamic>> runTask(String taskId);
  Future<Map<String, dynamic>> runTasks(List<String> taskIds);
  Future<Map<String, dynamic>> retry(String taskId);
  Future<Map<String, dynamic>> retryTasks(List<String> taskIds);
  Future<Map<String, dynamic>> cancel(String taskId);
  Future<Map<String, dynamic>> cancelTasks(List<String> taskIds);
  Future<Map<String, dynamic>> removeTasks(List<String> taskIds);
  Future<Map<String, dynamic>> clearCompleted();
  Future<Map<String, dynamic>> settings();
  Future<Map<String, dynamic>> setTarget(String path);
  Future<Map<String, dynamic>> recover();
}

class DownloadBridge implements DownloadBridgeClient {
  @override
  Future<Map<String, dynamic>> summary() => _run('summary');

  @override
  Future<Map<String, dynamic>> tasks({String status = '', int limit = 1000}) =>
      _run('tasks', status: status, limit: limit);

  @override
  Future<Map<String, dynamic>> enqueue(String externalId) =>
      _run('enqueue', externalId: externalId);

  @override
  Future<Map<String, dynamic>> enqueueWanted() => _run('enqueue_wanted');

  @override
  Future<Map<String, dynamic>> enqueueSelected(List<String> externalIds) =>
      _runAction('enqueue_selected', externalIds: externalIds);

  @override
  Future<Map<String, dynamic>> runQueue() => _run('run');

  @override
  Future<Map<String, dynamic>> runTask(String taskId) =>
      _run('run_task', taskId: taskId);

  @override
  Future<Map<String, dynamic>> runTasks(List<String> taskIds) =>
      _runAction('run_tasks', taskIds: taskIds);

  @override
  Future<Map<String, dynamic>> retry(String taskId) => _run('retry', taskId: taskId);

  @override
  Future<Map<String, dynamic>> retryTasks(List<String> taskIds) =>
      _runAction('retry_tasks', taskIds: taskIds);

  @override
  Future<Map<String, dynamic>> cancel(String taskId) => _run('cancel', taskId: taskId);

  @override
  Future<Map<String, dynamic>> cancelTasks(List<String> taskIds) =>
      _runAction('cancel_tasks', taskIds: taskIds);

  @override
  Future<Map<String, dynamic>> removeTasks(List<String> taskIds) =>
      _runAction('remove_tasks', taskIds: taskIds);

  @override
  Future<Map<String, dynamic>> clearCompleted() => _run('clear_completed');

  @override
  Future<Map<String, dynamic>> settings() => _run('settings');

  @override
  Future<Map<String, dynamic>> setTarget(String path) =>
      _run('set_target', targetPath: path);

  @override
  Future<Map<String, dynamic>> recover() => _run('recover');

  Future<Map<String, dynamic>> _run(
    String command, {
    String? externalId,
    String? taskId,
    String? status,
    int? limit,
    String? targetPath,
  }) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePythonCommand(repoRoot);
    final separator = Platform.pathSeparator;
    final srcPath = '$repoRoot${separator}src';
    final existingPythonPath = Platform.environment['PYTHONPATH'];
    final environment = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': existingPythonPath == null || existingPythonPath.isEmpty
          ? srcPath
          : '$srcPath${Platform.isWindows ? ';' : ':'}$existingPythonPath',
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    };
    environment.remove('YANDEX_MUSIC_TOKEN');
    if (targetPath != null && targetPath.isNotEmpty) {
      environment['MUSICARK_DOWNLOAD_TARGET'] = targetPath;
    } else {
      environment.remove('MUSICARK_DOWNLOAD_TARGET');
    }

    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.download.bridge',
      '--base-dir',
      repoRoot,
      command,
      if (externalId != null && externalId.isNotEmpty) ...['--external-id', externalId],
      if (taskId != null && taskId.isNotEmpty) ...['--task-id', taskId],
      if (status != null && status.isNotEmpty) ...['--status', status],
      if (limit != null) ...['--limit', '$limit'],
    ];

    return _runPython(
      python: python,
      args: args,
      repoRoot: repoRoot,
      environment: environment,
    );
  }

  Future<Map<String, dynamic>> _runAction(
    String command, {
    List<String> taskIds = const [],
    List<String> externalIds = const [],
  }) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePythonCommand(repoRoot);
    final separator = Platform.pathSeparator;
    final srcPath = '$repoRoot${separator}src';
    final existingPythonPath = Platform.environment['PYTHONPATH'];
    final environment = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': existingPythonPath == null || existingPythonPath.isEmpty
          ? srcPath
          : '$srcPath${Platform.isWindows ? ';' : ':'}$existingPythonPath',
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    };
    environment.remove('YANDEX_MUSIC_TOKEN');

    final cleanTaskIds = taskIds.map((id) => id.trim()).where((id) => id.isNotEmpty).toSet().toList();
    final cleanExternalIds =
        externalIds.map((id) => id.trim()).where((id) => id.isNotEmpty).toSet().toList();
    final batchFile = File(
      '${Directory.systemTemp.path}${separator}musicark-download-batch-$pid-${DateTime.now().microsecondsSinceEpoch}.json',
    );
    try {
      await batchFile.writeAsString(
        jsonEncode({
          'taskIds': cleanTaskIds,
          'externalIds': cleanExternalIds,
        }),
        encoding: utf8,
        flush: true,
      );
      final args = <String>[
        ...python.prefixArgs,
        '-m',
        'musicark.download.actions_bridge',
        '--base-dir',
        repoRoot,
        '--batch-file',
        batchFile.path,
        command,
      ];
      return await _runPython(
        python: python,
        args: args,
        repoRoot: repoRoot,
        environment: environment,
      );
    } finally {
      try {
        await batchFile.delete();
      } on FileSystemException {
        // The batch file contains only task/provider IDs and can be reclaimed by the OS.
      }
    }
  }

  Future<Map<String, dynamic>> _runPython({
    required _PythonCommand python,
    required List<String> args,
    required String repoRoot,
    required Map<String, String> environment,
  }) async {
    final result = await Process.run(
      python.executable,
      args,
      runInShell: false,
      workingDirectory: repoRoot,
      environment: environment,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    final stdoutText = (result.stdout ?? '').toString().trim();
    final stderrText = (result.stderr ?? '').toString().trim();
    Map<String, dynamic>? payload;
    if (stdoutText.isNotEmpty) {
      try {
        final decoded = jsonDecode(stdoutText);
        if (decoded is Map) payload = Map<String, dynamic>.from(decoded);
      } on FormatException {
        payload = null;
      }
    }
    final rawError = payload?['error'];
    if (rawError is Map) {
      final error = Map<String, dynamic>.from(rawError);
      throw DownloadBridgeException(
        (error['code'] ?? 'unexpected_error').toString(),
        (error['message'] ?? stderrText).toString(),
      );
    }
    if (result.exitCode != 0 || payload == null) {
      throw DownloadBridgeException(
        'unexpected_error',
        stderrText.isNotEmpty ? stderrText : stdoutText,
      );
    }
    return payload;
  }

  String _resolveRepoRoot() {
    final override = Platform.environment['MUSICARK_REPO_ROOT']?.trim();
    if (override != null && override.isNotEmpty) {
      final directory = Directory(override);
      if (_looksLikeRepoRoot(directory)) return directory.absolute.path;
    }
    final starts = <Directory>{
      Directory.current.absolute,
      File(Platform.resolvedExecutable).parent.absolute,
    };
    for (final start in starts) {
      var current = start;
      while (true) {
        if (_looksLikeRepoRoot(current)) return current.path;
        final parent = current.parent;
        if (parent.path == current.path) break;
        current = parent;
      }
    }
    throw const DownloadBridgeException(
      'repo_root_not_found',
      'MusicArk repository root was not found.',
    );
  }

  bool _looksLikeRepoRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File('${directory.path}${separator}src${separator}musicark${separator}download${separator}bridge.py').existsSync();
  }

  Future<_PythonCommand> _resolvePythonCommand(String repoRoot) async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) {
      final explicit = _PythonCommand(override);
      if (await _pythonWorks(explicit)) return explicit;
    }
    final separator = Platform.pathSeparator;
    final repoVenv = Platform.isWindows
        ? '$repoRoot${separator}.venv${separator}Scripts${separator}python.exe'
        : '$repoRoot${separator}.venv${separator}bin${separator}python';
    if (File(repoVenv).existsSync()) {
      final local = _PythonCommand(repoVenv);
      if (await _pythonWorks(local)) return local;
    }
    final candidates = Platform.isWindows
        ? const [_PythonCommand('python'), _PythonCommand('py', prefixArgs: ['-3'])]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final candidate in candidates) {
      if (await _pythonWorks(candidate)) return candidate;
    }
    throw const DownloadBridgeException('python_not_found', 'Python was not found.');
  }

  Future<bool> _pythonWorks(_PythonCommand candidate) async {
    try {
      final result = await Process.run(
        candidate.executable,
        [...candidate.prefixArgs, '--version'],
        runInShell: false,
      );
      return result.exitCode == 0;
    } on ProcessException {
      return false;
    }
  }
}

class _PythonCommand {
  const _PythonCommand(this.executable, {this.prefixArgs = const []});
  final String executable;
  final List<String> prefixArgs;
}

class DownloadBridgeException implements Exception {
  const DownloadBridgeException(this.code, this.message);
  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}

class FakeDownloadBridge implements DownloadBridgeClient {
  FakeDownloadBridge({this.configured = true});

  bool configured;
  bool runCalled = false;
  int runTaskCalls = 0;
  String? lastRunTaskId;
  final List<String> runTaskIds = [];
  int enqueueCalls = 0;
  int enqueueWantedCalls = 0;
  String? lastEnqueuedId;
  String? selectedPath;
  final List<List<String>> retryBatches = [];
  final List<List<String>> cancelBatches = [];
  final List<List<String>> removeBatches = [];
  final List<List<String>> runBatches = [];
  final List<List<String>> enqueueSelectedBatches = [];

  final List<Map<String, dynamic>> items = [
    {
      'id': 'queued-1',
      'provider': 'yandex_music',
      'externalId': '101',
      'title': 'Queued Song',
      'artists': ['Artist'],
      'status': 'queued',
      'progress': null,
      'downloadedBytes': 0,
      'totalBytes': null,
      'targetPath': r'C:\Music\MusicArk\Artist - Queued Song [yandex_101].mp3',
      'error': null,
      'canRetry': false,
      'canCancel': true,
    },
    {
      'id': 'running-1',
      'provider': 'yandex_music',
      'externalId': '102',
      'title': 'Running Song',
      'artists': ['Artist'],
      'status': 'running',
      'progress': 0.82,
      'downloadedBytes': 12400000,
      'totalBytes': 15100000,
      'targetPath': r'C:\Music\MusicArk\Artist - Running Song [yandex_102].mp3',
      'error': null,
      'canRetry': false,
      'canCancel': true,
    },
    {
      'id': 'failed-1',
      'provider': 'yandex_music',
      'externalId': '103',
      'title': 'Failed Song',
      'artists': ['Artist'],
      'status': 'failed',
      'progress': null,
      'downloadedBytes': 0,
      'totalBytes': null,
      'targetPath': r'C:\Music\MusicArk\Artist - Failed Song [yandex_103].mp3',
      'errorCode': 'network_error',
      'error': 'Network error while downloading track.',
      'canRetry': true,
      'canCancel': false,
    },
  ];

  @override
  Future<Map<String, dynamic>> summary() async => {
        'counts': {
          'queued': items.where((e) => e['status'] == 'queued').length,
          'running': items.where((e) => e['status'] == 'running').length,
          'completed': items.where((e) => e['status'] == 'completed').length,
          'failed': items.where((e) => e['status'] == 'failed' || e['status'] == 'needs_review').length,
          'cancelled': items.where((e) => e['status'] == 'cancelled').length,
          'skipped': items.where((e) => e['status'] == 'skipped').length,
          'total': items.length,
        },
        'settings': await settings(),
      };

  @override
  Future<Map<String, dynamic>> tasks({String status = '', int limit = 1000}) async {
    final filtered = status.isEmpty ? items : items.where((e) => e['status'] == status).toList();
    return {'count': filtered.length, 'items': filtered.take(limit).toList()};
  }

  @override
  Future<Map<String, dynamic>> enqueue(String externalId) async {
    enqueueCalls++;
    lastEnqueuedId = externalId;
    return {
      'created': true,
      'task': {
        'id': 'direct-$externalId',
        'provider': 'yandex_music',
        'externalId': externalId,
        'status': 'queued',
      },
    };
  }

  @override
  Future<Map<String, dynamic>> enqueueWanted() async {
    enqueueWantedCalls++;
    final id = 'wanted-$enqueueWantedCalls';
    final item = <String, dynamic>{
      'id': id,
      'provider': 'yandex_music',
      'externalId': 'wanted-$enqueueWantedCalls',
      'title': 'Wanted Song $enqueueWantedCalls',
      'artists': ['Artist'],
      'status': 'queued',
      'progress': null,
      'downloadedBytes': 0,
      'totalBytes': null,
      'targetPath': r'C:\Music\MusicArk\Wanted.mp3',
      'error': null,
      'canRetry': false,
      'canCancel': true,
    };
    items.add(item);
    return {'created': 1, 'existing': 0, 'items': [item]};
  }

  @override
  Future<Map<String, dynamic>> enqueueSelected(List<String> externalIds) async {
    final clean = externalIds.toSet().toList();
    enqueueSelectedBatches.add(clean);
    final created = <Map<String, dynamic>>[];
    for (final externalId in clean) {
      final existing = items.where((item) => '${item['externalId']}' == externalId && item['status'] == 'queued').toList();
      if (existing.isNotEmpty) {
        created.add(existing.first);
        continue;
      }
      final item = <String, dynamic>{
        'id': 'selected-$externalId',
        'provider': 'yandex_music',
        'externalId': externalId,
        'title': 'Selected $externalId',
        'artists': ['Artist'],
        'status': 'queued',
        'progress': null,
        'downloadedBytes': 0,
        'totalBytes': null,
        'targetPath': r'C:\Music\MusicArk\Selected.mp3',
        'error': null,
        'canRetry': false,
        'canCancel': true,
      };
      items.add(item);
      created.add(item);
    }
    return _batchResult(clean, created, const []);
  }

  @override
  Future<Map<String, dynamic>> runQueue() async {
    runCalled = true;
    return {'processed': 0, 'items': []};
  }

  @override
  Future<Map<String, dynamic>> runTask(String taskId) async {
    runTaskCalls++;
    lastRunTaskId = taskId;
    runTaskIds.add(taskId);
    Map<String, dynamic>? existing;
    for (final item in items) {
      if (item['id'] == taskId) {
        existing = item;
        break;
      }
    }
    if (existing != null) {
      existing['status'] = 'completed';
      existing['progress'] = 1.0;
      existing['canRetry'] = false;
      existing['canCancel'] = false;
      return {'task': existing};
    }
    return {
      'task': {
        'id': taskId,
        'externalId': taskId.startsWith('direct-') ? taskId.substring(7) : '',
        'status': 'completed',
      },
    };
  }

  @override
  Future<Map<String, dynamic>> runTasks(List<String> taskIds) async {
    final clean = taskIds.toSet().toList();
    runBatches.add(clean);
    final result = <Map<String, dynamic>>[];
    for (final taskId in clean) {
      final payload = await runTask(taskId);
      final raw = payload['task'];
      if (raw is Map) result.add(Map<String, dynamic>.from(raw));
    }
    return _batchResult(clean, result, const []);
  }

  @override
  Future<Map<String, dynamic>> retry(String taskId) async {
    final item = items.firstWhere((e) => e['id'] == taskId);
    item['status'] = 'queued';
    item['error'] = null;
    item['errorCode'] = null;
    item['canRetry'] = false;
    item['canCancel'] = true;
    return {'task': item};
  }

  @override
  Future<Map<String, dynamic>> retryTasks(List<String> taskIds) async {
    final clean = taskIds.toSet().toList();
    retryBatches.add(clean);
    final result = <Map<String, dynamic>>[];
    for (final taskId in clean) {
      final payload = await retry(taskId);
      result.add(Map<String, dynamic>.from(payload['task'] as Map));
    }
    return _batchResult(clean, result, const []);
  }

  @override
  Future<Map<String, dynamic>> cancel(String taskId) async {
    final item = items.firstWhere((e) => e['id'] == taskId);
    item['status'] = 'cancelled';
    item['canCancel'] = false;
    return {'task': item};
  }

  @override
  Future<Map<String, dynamic>> cancelTasks(List<String> taskIds) async {
    final clean = taskIds.toSet().toList();
    cancelBatches.add(clean);
    final result = <Map<String, dynamic>>[];
    for (final taskId in clean) {
      final payload = await cancel(taskId);
      result.add(Map<String, dynamic>.from(payload['task'] as Map));
    }
    return _batchResult(clean, result, const []);
  }

  @override
  Future<Map<String, dynamic>> removeTasks(List<String> taskIds) async {
    final clean = taskIds.toSet().toList();
    removeBatches.add(clean);
    final removed = <Map<String, dynamic>>[];
    final errors = <Map<String, dynamic>>[];
    for (final taskId in clean) {
      final index = items.indexWhere((item) => item['id'] == taskId);
      if (index < 0) {
        errors.add({'id': taskId, 'code': 'invalid_task', 'message': 'Task not found.'});
        continue;
      }
      final status = '${items[index]['status']}';
      if (status != 'failed' && status != 'needs_review') {
        errors.add({'id': taskId, 'code': 'not_removable', 'message': 'Task is active.'});
        continue;
      }
      items.removeAt(index);
      removed.add({'id': taskId, 'status': 'removed'});
    }
    return _batchResult(clean, removed, errors);
  }

  @override
  Future<Map<String, dynamic>> clearCompleted() async {
    final before = items.length;
    items.removeWhere((e) => e['status'] == 'completed');
    return {'removed': before - items.length};
  }

  @override
  Future<Map<String, dynamic>> settings() async {
    final target = selectedPath ?? r'C:\Music';
    return {
      'targetConfigured': configured,
      'rootId': configured ? 1 : null,
      'rootPath': configured ? target : null,
      'targetPath': configured ? target : null,
    };
  }

  @override
  Future<Map<String, dynamic>> setTarget(String path) async {
    configured = true;
    selectedPath = path;
    return settings();
  }

  @override
  Future<Map<String, dynamic>> recover() async => {'recovered': 0};

  Map<String, dynamic> _batchResult(
    List<String> requested,
    List<Map<String, dynamic>> result,
    List<Map<String, dynamic>> errors,
  ) {
    final skipped = result.where((item) => item['status'] == 'skipped').length;
    return {
      'requested': requested.length,
      'processed': result.length + errors.length,
      'succeeded': result.length - skipped,
      'failed': errors.length,
      'skipped': skipped,
      'items': result,
      'errors': errors,
    };
  }
}
