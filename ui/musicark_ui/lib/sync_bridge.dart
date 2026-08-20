import 'dart:convert';
import 'dart:io';

abstract interface class SyncBridgeClient {
  Future<Map<String, dynamic>> scopes();
  Future<Map<String, dynamic>> target();
  Future<Map<String, dynamic>> setTarget(String path);
  Future<Map<String, dynamic>> createPlan({
    required String scopeType,
    String? scopeId,
  });
  Future<Map<String, dynamic>> current();
  Future<Map<String, dynamic>> plan(String planId);
  Future<Map<String, dynamic>> history({int limit = 20});
  Future<Map<String, dynamic>> apply(
    String planId, {
    required bool confirm,
    bool rightsConfirmed = false,
  });
  Future<Map<String, dynamic>> cancel(String planId);
  Future<Map<String, dynamic>> setAction(String externalId, String action);
  Future<Map<String, dynamic>> recoveryTracks({
    String filter = 'all',
    int limit = 500,
    int offset = 0,
  });
}

class SyncBridge implements SyncBridgeClient {
  @override
  Future<Map<String, dynamic>> scopes() => _run('scopes');

  @override
  Future<Map<String, dynamic>> target() => _run('target');

  @override
  Future<Map<String, dynamic>> setTarget(String path) =>
      _run('set_target', targetPath: path);

  @override
  Future<Map<String, dynamic>> createPlan({
    required String scopeType,
    String? scopeId,
  }) => _run('create', scopeType: scopeType, scopeId: scopeId);

  @override
  Future<Map<String, dynamic>> current() => _run('current');

  @override
  Future<Map<String, dynamic>> plan(String planId) =>
      _run('plan', planId: planId);

  @override
  Future<Map<String, dynamic>> history({int limit = 20}) =>
      _run('history', limit: limit);

  @override
  Future<Map<String, dynamic>> apply(
    String planId, {
    required bool confirm,
    bool rightsConfirmed = false,
  }) => _run(
    'apply',
    planId: planId,
    confirm: confirm,
    rightsConfirmed: rightsConfirmed,
  );

  @override
  Future<Map<String, dynamic>> cancel(String planId) =>
      _run('cancel', planId: planId);

  @override
  Future<Map<String, dynamic>> setAction(String externalId, String action) =>
      _run('set_action', externalId: externalId, action: action);

  @override
  Future<Map<String, dynamic>> recoveryTracks({
    String filter = 'all',
    int limit = 500,
    int offset = 0,
  }) => _run(
    'recovery_tracks',
    filter: filter,
    limit: limit,
    offset: offset,
  );

  Future<Map<String, dynamic>> _run(
    String command, {
    String? planId,
    String? scopeType,
    String? scopeId,
    String? targetPath,
    String? externalId,
    String? action,
    String? filter,
    int? limit,
    int? offset,
    bool confirm = false,
    bool rightsConfirmed = false,
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

    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.sync.bridge',
      '--base-dir',
      repoRoot,
      command,
      if (planId != null && planId.isNotEmpty) ...['--plan-id', planId],
      if (scopeType != null && scopeType.isNotEmpty) ...[
        '--scope-type',
        scopeType,
      ],
      if (scopeId != null && scopeId.isNotEmpty) ...['--scope-id', scopeId],
      if (targetPath != null && targetPath.isNotEmpty) ...[
        '--target-path',
        targetPath,
      ],
      if (externalId != null && externalId.isNotEmpty) ...[
        '--external-id',
        externalId,
      ],
      if (action != null && action.isNotEmpty) ...['--action', action],
      if (filter != null && filter.isNotEmpty) ...['--filter', filter],
      if (limit != null) ...['--limit', '$limit'],
      if (offset != null) ...['--offset', '$offset'],
      if (confirm) '--confirm',
      if (rightsConfirmed) '--rights-confirmed',
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
      throw SyncBridgeException(
        (error['code'] ?? 'unexpected_error').toString(),
        (error['message'] ?? stderrText).toString(),
      );
    }
    if (result.exitCode != 0 || payload == null) {
      throw SyncBridgeException(
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
    throw const SyncBridgeException(
      'repo_root_not_found',
      'MusicArk repository root was not found.',
    );
  }

  bool _looksLikeRepoRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File(
          '${directory.path}${separator}pyproject.toml',
        ).existsSync() &&
        File(
          '${directory.path}${separator}src${separator}musicark${separator}sync${separator}bridge.py',
        ).existsSync();
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
        ? const [
            _PythonCommand('python'),
            _PythonCommand('py', prefixArgs: ['-3']),
          ]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final candidate in candidates) {
      if (await _pythonWorks(candidate)) return candidate;
    }
    throw const SyncBridgeException('python_not_found', 'Python was not found.');
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

class SyncBridgeException implements Exception {
  const SyncBridgeException(this.code, this.message);
  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}

class FakeSyncBridge implements SyncBridgeClient {
  FakeSyncBridge({this.targetConfigured = true});

  bool targetConfigured;
  int createCalls = 0;
  int applyCalls = 0;
  int cancelCalls = 0;
  String? lastAction;
  String? lastActionId;
  bool lastRightsConfirmed = false;
  String targetPath = r'C:\Music';
  Map<String, dynamic>? currentPlan;

  List<Map<String, dynamic>> scopeItems = [
    {'type': 'all', 'id': null, 'title': 'Вся библиотека'},
    {'type': 'liked', 'id': 'liked', 'title': 'Мне нравится'},
    {'type': 'playlist', 'id': 'playlist:focus', 'title': 'Focus'},
  ];

  @override
  Future<Map<String, dynamic>> scopes() async => {'items': scopeItems};

  @override
  Future<Map<String, dynamic>> target() async => {
    'targetConfigured': targetConfigured,
    'rootId': targetConfigured ? 1 : null,
    'rootPath': targetConfigured ? targetPath : null,
    'targetPath': targetConfigured ? targetPath : null,
  };

  @override
  Future<Map<String, dynamic>> setTarget(String path) async {
    targetConfigured = true;
    targetPath = path;
    return target();
  }

  Map<String, dynamic> samplePlan({String status = 'planned'}) => {
    'id': 'plan-1',
    'createdAt': '2026-08-16T18:00:00Z',
    'plannerVersion': 2,
    'scopeType': 'all',
    'scopeId': null,
    'scopeLabel': 'Вся библиотека',
    'targetRootId': targetConfigured ? 1 : null,
    'targetFolder': targetConfigured ? targetPath : null,
    'status': status,
    'legacy': false,
    'summary': {
      'desiredTracks': 10,
      'alreadyCovered': 3,
      'readyToDownload': 3,
      'alreadyQueued': 0,
      'missingUndecided': 2,
      'ignoredMissing': 0,
      'identityReview': 1,
      'notAnalyzed': 1,
      'variantIssues': 1,
      'localOnly': 1,
      'currentCoveragePercent': 30.0,
      'projectedCoveragePercent': 60.0,
      'operationCount': 9,
      'blockerCount': 5,
      'unavailableTracks': 1,
      'unavailableRecoverable': 1,
      'unavailableMissingLocal': 0,
      'censoredTracks': 0,
      'censoredRecoverable': 0,
      'censoredNeedsReview': 0,
      'readyToUpload': 0,
      'uploadBlocked': 0,
      'uploadByRole': {'censored': 0, 'unavailable': 0},
    },
    'result': {},
    'operations': [
      {
        'id': 1,
        'type': 'enqueue_download',
        'externalId': '1',
        'reason': 'missing_wanted',
        'status': 'pending',
        'metadata': {
          'title': 'Download Me',
          'artists': ['Artist'],
          'album': 'Album',
          'coverageStatus': 'missing',
          'userAction': 'wanted',
        },
        'result': {},
      },
      {
        'id': 2,
        'type': 'user_decision_required',
        'externalId': '2',
        'reason': 'missing_unreviewed',
        'status': 'informational',
        'metadata': {
          'title': 'Decide Me',
          'artists': ['Artist'],
          'coverageStatus': 'missing',
          'userAction': 'unreviewed',
        },
        'result': {},
      },
      {
        'id': 3,
        'type': 'review_identity',
        'externalId': '3',
        'reason': 'identity_needs_review',
        'status': 'informational',
        'metadata': {'title': 'Review Identity', 'artists': ['Artist']},
        'result': {},
      },
      {
        'id': 4,
        'type': 'review_identity',
        'externalId': '4',
        'reason': 'matching_required',
        'status': 'informational',
        'metadata': {
          'title': 'Analyze Me',
          'artists': ['Artist'],
          'matchingRequired': true,
        },
        'result': {},
      },
      {
        'id': 5,
        'type': 'review_variant',
        'externalId': '5',
        'reason': 'variant_different_version',
        'status': 'informational',
        'metadata': {
          'title': 'Different Version',
          'artists': ['Artist'],
          'coverageStatus': 'covered',
          'variantStatus': 'different_version',
        },
        'result': {},
      },
      {
        'id': 6,
        'type': 'local_only',
        'externalId': '99',
        'reason': 'local_only',
        'status': 'informational',
        'metadata': {'title': 'Local Only', 'artists': ['Artist']},
        'result': {},
      },
    ],
  };

  @override
  Future<Map<String, dynamic>> createPlan({
    required String scopeType,
    String? scopeId,
  }) async {
    createCalls++;
    currentPlan = samplePlan();
    currentPlan!['scopeType'] = scopeType;
    currentPlan!['scopeId'] = scopeId;
    return currentPlan!;
  }

  @override
  Future<Map<String, dynamic>> current() async => {'plan': currentPlan};

  @override
  Future<Map<String, dynamic>> plan(String planId) async =>
      currentPlan ?? samplePlan();

  @override
  Future<Map<String, dynamic>> history({int limit = 20}) async => {
    'items': currentPlan == null
        ? <Map<String, dynamic>>[]
        : [
            {
              'id': currentPlan!['id'],
              'createdAt': currentPlan!['createdAt'],
              'scopeLabel': currentPlan!['scopeLabel'],
              'status': currentPlan!['status'],
              'operationCount': currentPlan!['summary']['operationCount'],
              'legacy': false,
            },
          ],
  };

  @override
  Future<Map<String, dynamic>> apply(
    String planId, {
    required bool confirm,
    bool rightsConfirmed = false,
  }) async {
    if (!confirm) {
      throw const SyncBridgeException(
        'confirmation_required',
        'confirm required',
      );
    }
    applyCalls++;
    lastRightsConfirmed = rightsConfirmed;
    currentPlan ??= samplePlan();
    currentPlan!['status'] = 'applied';
    currentPlan!['result'] = {
      'enqueued': 3,
      'skipped': 0,
      'failed': 0,
      'taskIds': ['task-1'],
      'downloadsAutoStarted': false,
      'downloads': {
        'enqueued': 3,
        'skipped': 0,
        'failed': 0,
        'taskIds': ['task-1'],
        'items': const [],
      },
      'uploads': {
        'total': 0,
        'verified': 0,
        'processing': 0,
        'deliveryUnknown': 0,
        'failed': 0,
        'unsupported': 0,
        'ambiguous': 0,
        'skipped': 0,
        'items': const [],
      },
    };
    return {
      'plan': currentPlan,
      'result': currentPlan!['result'],
      'repeated': false,
    };
  }

  @override
  Future<Map<String, dynamic>> cancel(String planId) async {
    cancelCalls++;
    currentPlan ??= samplePlan();
    currentPlan!['status'] = 'cancelled';
    return currentPlan!;
  }

  @override
  Future<Map<String, dynamic>> recoveryTracks({
    String filter = 'all',
    int limit = 500,
    int offset = 0,
  }) async {
    final items = <Map<String, dynamic>>[
      {
        'externalId': 'unavailable-1',
        'title': 'Unavailable Track',
        'artists': ['Artist'],
        'album': 'Album',
        'collections': [
          {'playlistKind': 'focus', 'title': 'Focus'},
        ],
        'providerAvailability': 'unavailable',
        'localFileId': 77,
        'localFileName': 'Unavailable Track.mp3',
        'localExtension': '.mp3',
        'recoveryState': 'unavailable_local_available',
        'localMp3Ready': true,
      },
    ];
    return {
      'summary': {
        'unavailableTracks': 1,
        'unavailableRecoverable': 1,
        'unavailableMissingLocal': 0,
        'censoredTracks': 0,
        'censoredRecoverable': 0,
        'censoredNeedsReview': 0,
        'needsReview': 0,
      },
      'count': items.length,
      'items': items,
    };
  }

  @override
  Future<Map<String, dynamic>> setAction(
    String externalId,
    String action,
  ) async {
    lastActionId = externalId;
    lastAction = action;
    if (currentPlan != null) currentPlan!['status'] = 'stale';
    return {'externalId': externalId, 'action': action};
  }
}
