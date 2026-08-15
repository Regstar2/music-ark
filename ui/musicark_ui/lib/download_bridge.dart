import 'dart:convert';
import 'dart:io';

abstract interface class DownloadBridgeClient {
  Future<Map<String, dynamic>> summary();
  Future<Map<String, dynamic>> tasks({String status = '', int limit = 1000});
  Future<Map<String, dynamic>> enqueue(String externalId);
  Future<Map<String, dynamic>> enqueueWanted();
  Future<Map<String, dynamic>> runQueue();
  Future<Map<String, dynamic>> retry(String taskId);
  Future<Map<String, dynamic>> cancel(String taskId);
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
  Future<Map<String, dynamic>> runQueue() => _run('run');
  @override
  Future<Map<String, dynamic>> retry(String taskId) => _run('retry', taskId: taskId);
  @override
  Future<Map<String, dynamic>> cancel(String taskId) => _run('cancel', taskId: taskId);
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
    // Production downloads must obtain the Yandex token from SystemCredentialStore.
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
  int enqueueWantedCalls = 0;
  String? selectedPath;
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
          'failed': items.where((e) => e['status'] == 'failed').length,
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
  Future<Map<String, dynamic>> enqueue(String externalId) async => {'created': true};

  @override
  Future<Map<String, dynamic>> enqueueWanted() async {
    enqueueWantedCalls++;
    return {'created': 1, 'existing': 0};
  }

  @override
  Future<Map<String, dynamic>> runQueue() async {
    runCalled = true;
    return {'processed': 0, 'items': []};
  }

  @override
  Future<Map<String, dynamic>> retry(String taskId) async {
    final item = items.firstWhere((e) => e['id'] == taskId);
    item['status'] = 'queued';
    item['error'] = null;
    item['canRetry'] = false;
    item['canCancel'] = true;
    return {'task': item};
  }

  @override
  Future<Map<String, dynamic>> cancel(String taskId) async {
    final item = items.firstWhere((e) => e['id'] == taskId);
    item['status'] = 'cancelled';
    item['canCancel'] = false;
    return {'task': item};
  }

  @override
  Future<Map<String, dynamic>> clearCompleted() async {
    final before = items.length;
    items.removeWhere((e) => e['status'] == 'completed');
    return {'removed': before - items.length};
  }

  @override
  Future<Map<String, dynamic>> settings() async {
    final root = selectedPath ?? r'C:\Music';
    return {
      'targetConfigured': configured,
      'rootId': configured ? 1 : null,
      'rootPath': configured ? root : null,
      'targetPath': configured ? '$root\\MusicArk' : null,
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
}
