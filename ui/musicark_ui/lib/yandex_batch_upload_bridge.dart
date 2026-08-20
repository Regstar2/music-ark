import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';

const _payloadEnv = 'MUSICARK_YANDEX_UPLOAD_PAYLOAD';

abstract interface class YandexBatchUploadBridgeClient {
  Future<Map<String, dynamic>> managedPlaylists();
  Future<Map<String, dynamic>> ensureManagedPlaylists({required bool confirmCreate});
  Future<Map<String, dynamic>> setManagedPlaylist({required String role, required String playlistKind});
  Future<Map<String, dynamic>> clearManagedPlaylist(String role);
  Future<Map<String, dynamic>> uploadBatch({
    required List<int> localFileIds,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
    required String batchId,
    bool allowStaleReupload = false,
  });
  Future<Map<String, dynamic>> batchStatus(String batchId);
  Future<Map<String, dynamic>> cancelBatch(String batchId);
}

class YandexBatchUploadBridge implements YandexBatchUploadBridgeClient {
  const YandexBatchUploadBridge();

  @override
  Future<Map<String, dynamic>> managedPlaylists() =>
      _run('yandex_managed_playlists_get');

  @override
  Future<Map<String, dynamic>> ensureManagedPlaylists({required bool confirmCreate}) =>
      _run(
        'yandex_managed_playlists_ensure',
        payload: {'confirm_create': confirmCreate},
      );

  @override
  Future<Map<String, dynamic>> setManagedPlaylist({
    required String role,
    required String playlistKind,
  }) => _run(
    'yandex_managed_playlist_set',
    payload: {'role': role, 'playlist_kind': playlistKind},
  );

  @override
  Future<Map<String, dynamic>> clearManagedPlaylist(String role) =>
      _run('yandex_managed_playlist_clear', payload: {'role': role});

  @override
  Future<Map<String, dynamic>> uploadBatch({
    required List<int> localFileIds,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
    required String batchId,
    bool allowStaleReupload = false,
  }) => _run(
    'yandex_upload_batch',
    payload: {
      'local_file_ids': localFileIds,
      'playlist_kind': playlistKind,
      'confirm': confirm,
      'rights_confirmed': rightsConfirmed,
      'batch_id': batchId,
      'allow_stale_reupload': allowStaleReupload,
    },
  );

  @override
  Future<Map<String, dynamic>> batchStatus(String batchId) =>
      _run('yandex_upload_batch_status', payload: {'batch_id': batchId});

  @override
  Future<Map<String, dynamic>> cancelBatch(String batchId) =>
      _run('yandex_upload_batch_cancel', payload: {'batch_id': batchId});

  Future<Map<String, dynamic>> _run(
    String command, {
    Map<String, dynamic>? payload,
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
      if (payload != null) _payloadEnv: jsonEncode(payload),
    };
    environment.remove('YANDEX_MUSIC_TOKEN');

    final result = await Process.run(
      python.executable,
      [
        ...python.prefixArgs,
        '-m',
        'musicark.upload.bridge',
        '--base-dir',
        repoRoot,
        command,
      ],
      runInShell: false,
      workingDirectory: repoRoot,
      environment: environment,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    final stdoutText = (result.stdout ?? '').toString().trim();
    final stderrText = (result.stderr ?? '').toString().trim();
    Map<String, dynamic>? decoded;
    if (stdoutText.isNotEmpty) {
      try {
        final raw = jsonDecode(stdoutText);
        if (raw is Map) decoded = Map<String, dynamic>.from(raw);
      } on FormatException {
        decoded = null;
      }
    }
    final rawError = decoded?['error'];
    if (rawError is Map) {
      final error = Map<String, dynamic>.from(rawError);
      throw MusicArkBridgeException(
        (error['code'] ?? 'upload_bridge_failed').toString(),
        (error['message'] ?? '').toString(),
      );
    }
    if (result.exitCode != 0 || decoded == null) {
      throw MusicArkBridgeException(
        'upload_bridge_failed',
        stderrText.isNotEmpty ? stderrText : 'Yandex upload bridge failed.',
      );
    }
    return decoded;
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
    throw const MusicArkBridgeException(
      'repo_root_not_found',
      'MusicArk repository root was not found.',
    );
  }

  bool _looksLikeRepoRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File('${directory.path}${separator}src${separator}musicark${separator}upload${separator}bridge.py').existsSync();
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
    throw const MusicArkBridgeException('python_not_found', 'Python was not found.');
  }

  Future<bool> _pythonWorks(_PythonCommand command) async {
    try {
      final result = await Process.run(
        command.executable,
        [...command.prefixArgs, '--version'],
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

class FakeYandexBatchUploadBridge implements YandexBatchUploadBridgeClient {
  FakeYandexBatchUploadBridge({
    this.managedState = const {
      'canCreatePlaylists': false,
      'roles': [
        {
          'role': 'uploaded',
          'defaultTitle': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
          'configured': true,
          'playlistKind': '7',
          'title': 'ЗАГРУЖЕННЫЕ ТРЕКИ',
        },
      ],
      'availablePlaylists': [
        {'playlistKind': '7', 'title': 'ЗАГРУЖЕННЫЕ ТРЕКИ', 'trackCount': 0},
      ],
    },
    this.resultFactory,
  });

  Map<String, dynamic> managedState;
  Map<String, dynamic> Function(List<int> ids, String playlistKind)? resultFactory;
  final List<List<int>> uploadedBatches = [];
  final List<String> uploadedTargets = [];
  final List<String> cancelled = [];
  int statusCalls = 0;

  @override
  Future<Map<String, dynamic>> managedPlaylists() async =>
      Map<String, dynamic>.from(managedState);

  @override
  Future<Map<String, dynamic>> ensureManagedPlaylists({required bool confirmCreate}) async =>
      managedPlaylists();

  @override
  Future<Map<String, dynamic>> setManagedPlaylist({required String role, required String playlistKind}) async {
    final roles = (managedState['roles'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
    for (final item in roles) {
      if (item['role'] == role) {
        item['configured'] = true;
        item['playlistKind'] = playlistKind;
        item['title'] = playlistKind;
      }
    }
    managedState = {...managedState, 'roles': roles};
    return managedPlaylists();
  }

  @override
  Future<Map<String, dynamic>> clearManagedPlaylist(String role) async => managedPlaylists();

  @override
  Future<Map<String, dynamic>> uploadBatch({
    required List<int> localFileIds,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
    required String batchId,
    bool allowStaleReupload = false,
  }) async {
    uploadedBatches.add(List<int>.from(localFileIds));
    uploadedTargets.add(playlistKind);
    if (resultFactory != null) return resultFactory!(localFileIds, playlistKind);
    return {
      'batchId': batchId,
      'status': 'finished',
      'total': localFileIds.length,
      'completed': localFileIds.length,
      'counts': {
        'total': localFileIds.length,
        'verified': localFileIds.length,
        'processing': 0,
        'deliveryUnknown': 0,
        'failed': 0,
        'unsupported': 0,
        'ambiguous': 0,
        'skipped': 0,
        'cancelled': 0,
      },
      'items': [
        for (final id in localFileIds)
          {'localFileId': id, 'status': 'verified', 'result': {'state': 'verified'}},
      ],
      'retryableLocalFileIds': <int>[],
      'manualCheckLocalFileIds': <int>[],
      'concurrency': 1,
    };
  }

  @override
  Future<Map<String, dynamic>> batchStatus(String batchId) async {
    statusCalls++;
    return {
      'batchId': batchId,
      'status': 'running',
      'total': uploadedBatches.isEmpty ? 0 : uploadedBatches.last.length,
      'completed': 0,
      'counts': const {},
      'items': const [],
    };
  }

  @override
  Future<Map<String, dynamic>> cancelBatch(String batchId) async {
    cancelled.add(batchId);
    return {'accepted': true, 'batch': {'batchId': batchId}};
  }
}
