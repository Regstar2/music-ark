import 'dart:convert';
import 'dart:io';

abstract interface class CoverageBridgeClient {
  Future<Map<String, dynamic>> coverageSummary({String collectionId = ''});
  Future<Map<String, dynamic>> coverageCollections();
  Future<Map<String, dynamic>> coverageTracks({
    int limit = 100,
    int offset = 0,
    String status = 'missing',
    String collectionId = '',
    String search = '',
    String sort = 'artist',
    String userAction = '',
    String variantStatus = '',
  });
  Future<Map<String, dynamic>> coverageTrack(String externalId);
  Future<Map<String, dynamic>> coverageSetAction(String externalId, String action);
  Future<Map<String, dynamic>> coverageSetActions(List<String> externalIds, String action);
}

class CoverageBridge implements CoverageBridgeClient {
  @override
  Future<Map<String, dynamic>> coverageSummary({String collectionId = ''}) =>
      _run('coverage_summary', collectionId: collectionId);

  @override
  Future<Map<String, dynamic>> coverageCollections() =>
      _run('coverage_collections');

  @override
  Future<Map<String, dynamic>> coverageTracks({
    int limit = 100,
    int offset = 0,
    String status = 'missing',
    String collectionId = '',
    String search = '',
    String sort = 'artist',
    String userAction = '',
    String variantStatus = '',
  }) =>
      _run(
        'coverage_tracks',
        limit: limit,
        offset: offset,
        status: status,
        collectionId: collectionId,
        search: search,
        sort: sort,
        userAction: userAction,
        variantStatus: variantStatus,
      );

  @override
  Future<Map<String, dynamic>> coverageTrack(String externalId) =>
      _run('coverage_track', externalId: externalId);

  @override
  Future<Map<String, dynamic>> coverageSetAction(String externalId, String action) =>
      _run('coverage_set_action', externalId: externalId, action: action);

  @override
  Future<Map<String, dynamic>> coverageSetActions(
    List<String> externalIds,
    String action,
  ) =>
      _run(
        'coverage_set_actions',
        action: action,
        bulkExternalIds: externalIds,
      );

  Future<Map<String, dynamic>> _run(
    String command, {
    String? externalId,
    String? collectionId,
    String? status,
    String? search,
    String? sort,
    String? userAction,
    String? variantStatus,
    String? action,
    int? limit,
    int? offset,
    List<String>? bulkExternalIds,
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
      if (bulkExternalIds != null)
        'MUSICARK_COVERAGE_BULK': jsonEncode(bulkExternalIds),
    };
    environment.remove('YANDEX_MUSIC_TOKEN');
    environment.remove('MUSICARK_LOCAL_ROOT');

    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.mvp_bridge',
      '--base-dir',
      repoRoot,
      command,
      if (externalId != null && externalId.isNotEmpty) ...[
        '--external-id',
        externalId,
      ],
      if (collectionId != null && collectionId.isNotEmpty) ...[
        '--collection-id',
        collectionId,
      ],
      if (status != null && status.isNotEmpty) ...['--status', status],
      if (search != null && search.isNotEmpty) ...['--search', search],
      if (sort != null && sort.isNotEmpty) ...['--sort', sort],
      if (userAction != null && userAction.isNotEmpty) ...[
        '--user-action',
        userAction,
      ],
      if (variantStatus != null && variantStatus.isNotEmpty) ...[
        '--variant-status',
        variantStatus,
      ],
      if (action != null && action.isNotEmpty) ...['--action', action],
      if (limit != null) ...['--limit', '$limit'],
      if (offset != null) ...['--offset', '$offset'],
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
      throw CoverageBridgeException(
        (error['code'] ?? 'unexpected_error').toString(),
        (error['message'] ?? stderrText).toString(),
      );
    }
    if (result.exitCode != 0 || payload == null) {
      throw CoverageBridgeException(
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
    throw const CoverageBridgeException(
      'repo_root_not_found',
      'MusicArk repository root was not found.',
    );
  }

  bool _looksLikeRepoRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File(
          '${directory.path}${separator}src${separator}musicark${separator}mvp_bridge.py',
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
        ? const [_PythonCommand('python'), _PythonCommand('py', prefixArgs: ['-3'])]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final candidate in candidates) {
      if (await _pythonWorks(candidate)) return candidate;
    }
    throw const CoverageBridgeException(
      'python_not_found',
      'Python was not found.',
    );
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

class CoverageBridgeException implements Exception {
  const CoverageBridgeException(this.code, this.message);
  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}

class FakeCoverageBridge implements CoverageBridgeClient {
  FakeCoverageBridge();

  int summaryCalls = 0;
  int trackCalls = 0;
  int setActionCalls = 0;
  int bulkActionCalls = 0;

  final List<Map<String, dynamic>> items = [
    {
      'providerId': 'yandex_music',
      'externalId': '203',
      'provider': {
        'title': 'Missing Song',
        'artists': ['Missing Artist'],
        'album_title': 'Unknown',
        'duration_seconds': 240,
      },
      'collections': [
        {'id': 'liked', 'title': 'Мне нравится', 'position': 0},
        {'id': 'playlist:workout', 'title': 'Workout', 'position': 2},
      ],
      'coverageStatus': 'missing',
      'matchingStatus': 'unmatched',
      'confidence': 0.0,
      'reason': 'no_candidates',
      'variantStatus': null,
      'userAction': 'unreviewed',
      'local': null,
    },
    {
      'providerId': 'yandex_music',
      'externalId': '202',
      'provider': {
        'title': 'Review Song',
        'artists': ['Artist A'],
        'album_title': 'Album',
        'duration_seconds': 200,
      },
      'collections': [
        {'id': 'playlist:workout', 'title': 'Workout', 'position': 1},
      ],
      'coverageStatus': 'needs_review',
      'matchingStatus': 'conflict',
      'confidence': 0.82,
      'reason': 'ambiguous_top_candidates',
      'variantStatus': null,
      'userAction': 'unreviewed',
      'local': null,
    },
    {
      'providerId': 'yandex_music',
      'externalId': '204',
      'provider': {
        'title': 'New Song',
        'artists': ['New Artist'],
        'album_title': 'New Album',
        'duration_seconds': 180,
      },
      'collections': [
        {'id': 'liked', 'title': 'Мне нравится', 'position': 3},
      ],
      'coverageStatus': 'not_analyzed',
      'matchingStatus': null,
      'confidence': 0.0,
      'reason': '',
      'variantStatus': null,
      'userAction': 'unreviewed',
      'local': null,
    },
    {
      'providerId': 'yandex_music',
      'externalId': '201',
      'provider': {
        'title': 'Numb',
        'artists': ['Linkin Park'],
        'album_title': 'Meteora',
        'duration_seconds': 185,
      },
      'collections': [
        {'id': 'liked', 'title': 'Мне нравится', 'position': 4},
      ],
      'coverageStatus': 'covered',
      'matchingStatus': 'matched',
      'confidence': 0.97,
      'reason': 'auto_threshold_and_margin',
      'variantStatus': 'different_version',
      'userAction': 'unreviewed',
      'local': {
        'id': 1,
        'title': 'Numb',
        'artists': ['Linkin Park'],
        'album': 'Meteora',
        'path': r'C:\Music\Numb.flac',
      },
    },
  ];

  @override
  Future<Map<String, dynamic>> coverageSummary({String collectionId = ''}) async {
    summaryCalls++;
    final scoped = _scope(collectionId);
    int count(String status) =>
        scoped.where((item) => item['coverageStatus'] == status).length;
    return {
      'providerId': 'yandex_music',
      'collectionId': collectionId,
      'total': scoped.length,
      'covered': count('covered'),
      'missing': count('missing'),
      'needsReview': count('needs_review'),
      'notAnalyzed': count('not_analyzed'),
      'coveragePercent': scoped.isEmpty
          ? 0.0
          : count('covered') / scoped.length * 100.0,
      'matchingAnalyzedPercent': scoped.isEmpty
          ? 0.0
          : (scoped.length - count('not_analyzed')) / scoped.length * 100.0,
      'variantVerification': {
        'same': 0,
        'altered': 0,
        'differentVersion': count('covered'),
        'uncertain': 0,
        'notChecked': 0,
      },
      'missingActions': {
        'wanted': scoped
            .where(
              (item) =>
                  item['coverageStatus'] == 'missing' &&
                  item['userAction'] == 'wanted',
            )
            .length,
        'ignored': scoped
            .where(
              (item) =>
                  item['coverageStatus'] == 'missing' &&
                  item['userAction'] == 'ignored',
            )
            .length,
        'unreviewed': scoped
            .where(
              (item) =>
                  item['coverageStatus'] == 'missing' &&
                  item['userAction'] == 'unreviewed',
            )
            .length,
      },
    };
  }

  @override
  Future<Map<String, dynamic>> coverageCollections() async => {
    'items': [
      {
        'id': 'liked',
        'type': 'liked',
        'title': 'Мне нравится',
        'itemCount': 3,
      },
      {
        'id': 'playlist:workout',
        'type': 'playlist',
        'externalId': 'workout',
        'title': 'Workout',
        'itemCount': 2,
      },
    ],
  };

  List<Map<String, dynamic>> _scope(String collectionId) {
    if (collectionId.isEmpty) return List<Map<String, dynamic>>.from(items);
    return items
        .where(
          (item) => (item['collections'] as List).any(
            (raw) => (raw as Map)['id'] == collectionId,
          ),
        )
        .toList();
  }

  @override
  Future<Map<String, dynamic>> coverageTracks({
    int limit = 100,
    int offset = 0,
    String status = 'missing',
    String collectionId = '',
    String search = '',
    String sort = 'artist',
    String userAction = '',
    String variantStatus = '',
  }) async {
    var filtered = _scope(collectionId).where((item) {
      if (status.isNotEmpty && item['coverageStatus'] != status) return false;
      if (userAction.isNotEmpty && item['userAction'] != userAction) return false;
      if (variantStatus.isNotEmpty && item['variantStatus'] != variantStatus) {
        return false;
      }
      if (search.isNotEmpty) {
        final provider = Map<String, dynamic>.from(item['provider'] as Map);
        final collections = (item['collections'] as List)
            .map((raw) => (raw as Map)['title'].toString())
            .join(' ');
        final haystack =
            '${provider['title']} ${provider['artists']} ${provider['album_title']} $collections'
                .toLowerCase();
        if (!haystack.contains(search.toLowerCase())) return false;
      }
      return true;
    }).toList();

    if (sort == 'position') {
      filtered.sort((a, b) {
        int position(Map<String, dynamic> item) {
          final rows = (item['collections'] as List)
              .where((raw) => (raw as Map)['id'] == collectionId)
              .toList();
          return rows.isEmpty ? 1 << 30 : (rows.first as Map)['position'] as int;
        }

        return position(a).compareTo(position(b));
      });
    } else {
      String key(Map<String, dynamic> item) {
        final provider = Map<String, dynamic>.from(item['provider'] as Map);
        if (sort == 'title') return (provider['title'] ?? '').toString();
        if (sort == 'album') return (provider['album_title'] ?? '').toString();
        return ((provider['artists'] as List?)?.firstOrNull ?? '').toString();
      }

      filtered.sort((a, b) => key(a).compareTo(key(b)));
    }

    final total = filtered.length;
    final page = filtered.skip(offset).take(limit).toList();
    return {'count': total, 'limit': limit, 'offset': offset, 'items': page};
  }

  @override
  Future<Map<String, dynamic>> coverageTrack(String externalId) async {
    trackCalls++;
    final item = items.firstWhere((item) => item['externalId'] == externalId);
    return {
      'track': item,
      'matching': item['matchingStatus'] == null
          ? null
          : {
              'status': item['matchingStatus'],
              'reason': item['reason'],
              'confidence': item['confidence'],
              'candidates': <Map<String, dynamic>>[],
            },
      'variant': item['coverageStatus'] == 'covered'
          ? {'status': item['variantStatus'] ?? 'not_checked', 'applicable': true}
          : {
              'status': null,
              'applicable': false,
              'reason': 'no_accepted_local_identity',
            },
    };
  }

  @override
  Future<Map<String, dynamic>> coverageSetAction(
    String externalId,
    String action,
  ) async {
    setActionCalls++;
    final item = items.firstWhere((item) => item['externalId'] == externalId);
    item['userAction'] = action;
    return {
      'providerId': 'yandex_music',
      'externalId': externalId,
      'userAction': action,
    };
  }

  @override
  Future<Map<String, dynamic>> coverageSetActions(
    List<String> externalIds,
    String action,
  ) async {
    bulkActionCalls++;
    for (final item in items) {
      if (externalIds.contains(item['externalId'])) item['userAction'] = action;
    }
    return {'updated': externalIds.length, 'action': action};
  }
}

extension<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
