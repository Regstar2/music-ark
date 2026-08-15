import 'dart:convert';
import 'dart:io';

abstract interface class MatchingBridgeClient {
  Future<Map<String, dynamic>> matchingSummary();
  Future<Map<String, dynamic>> matchingRun();
  Future<Map<String, dynamic>> matchingResults({
    int limit = 100,
    int offset = 0,
    String status = '',
    String search = '',
    String sort = 'confidence',
  });
  Future<Map<String, dynamic>> matchingResult(String externalId);
  Future<Map<String, dynamic>> matchingAccept(String externalId, int localFileId);
  Future<Map<String, dynamic>> matchingReject(String externalId, int localFileId);

  Future<Map<String, dynamic>> variantCapabilities();
  Future<Map<String, dynamic>> variantSummary();
  Future<Map<String, dynamic>> variantRun(String externalId, {bool force = false});
  Future<Map<String, dynamic>> variantRunAllAvailable();
  Future<Map<String, dynamic>> variantResults({
    int limit = 500,
    int offset = 0,
    String status = '',
  });
  Future<Map<String, dynamic>> variantResult(String externalId);
}

class MatchingBridge implements MatchingBridgeClient {
  @override
  Future<Map<String, dynamic>> matchingSummary() => _run('matching_summary');

  @override
  Future<Map<String, dynamic>> matchingRun() => _run('matching_run');

  @override
  Future<Map<String, dynamic>> matchingResults({
    int limit = 100,
    int offset = 0,
    String status = '',
    String search = '',
    String sort = 'confidence',
  }) => _run(
    'matching_results',
    limit: limit,
    offset: offset,
    status: status,
    search: search,
    sort: sort,
  );

  @override
  Future<Map<String, dynamic>> matchingResult(String externalId) =>
      _run('matching_result', externalId: externalId);

  @override
  Future<Map<String, dynamic>> matchingAccept(String externalId, int localFileId) =>
      _run('matching_accept', externalId: externalId, localFileId: localFileId);

  @override
  Future<Map<String, dynamic>> matchingReject(String externalId, int localFileId) =>
      _run('matching_reject', externalId: externalId, localFileId: localFileId);

  @override
  Future<Map<String, dynamic>> variantCapabilities() => _run('variant_capabilities');

  @override
  Future<Map<String, dynamic>> variantSummary() => _run('variant_summary');

  @override
  Future<Map<String, dynamic>> variantRun(String externalId, {bool force = false}) =>
      _run('variant_run', externalId: externalId, force: force);

  @override
  Future<Map<String, dynamic>> variantRunAllAvailable() => _run('variant_run_all_available');

  @override
  Future<Map<String, dynamic>> variantResults({
    int limit = 500,
    int offset = 0,
    String status = '',
  }) => _run('variant_results', limit: limit, offset: offset, status: status);

  @override
  Future<Map<String, dynamic>> variantResult(String externalId) =>
      _run('variant_result', externalId: externalId);

  Future<Map<String, dynamic>> _run(
    String command, {
    String? externalId,
    int? localFileId,
    int? limit,
    int? offset,
    String? status,
    String? search,
    String? sort,
    bool force = false,
  }) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePythonCommand();
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
    environment.remove('MUSICARK_LOCAL_ROOT');

    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.mvp_bridge',
      '--base-dir',
      repoRoot,
      command,
      if (externalId != null && externalId.isNotEmpty) ...['--external-id', externalId],
      if (localFileId != null) ...['--local-file-id', '$localFileId'],
      if (limit != null) ...['--limit', '$limit'],
      if (offset != null) ...['--offset', '$offset'],
      if (status != null && status.isNotEmpty) ...['--status', status],
      if (search != null && search.isNotEmpty) ...['--search', search],
      if (sort != null && sort.isNotEmpty) ...['--sort', sort],
      if (force) '--force',
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
      throw MatchingBridgeException(
        (error['code'] ?? 'unexpected_error').toString(),
        (error['message'] ?? stderrText).toString(),
      );
    }
    if (result.exitCode != 0 || payload == null) {
      throw MatchingBridgeException(
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
    throw const MatchingBridgeException(
      'repo_root_not_found',
      'MusicArk repository root was not found.',
    );
  }

  bool _looksLikeRepoRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File('${directory.path}${separator}src${separator}musicark${separator}mvp_bridge.py').existsSync();
  }

  Future<_PythonCommand> _resolvePythonCommand() async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) return _PythonCommand(override);
    final candidates = Platform.isWindows
        ? const [_PythonCommand('python'), _PythonCommand('py', prefixArgs: ['-3'])]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final candidate in candidates) {
      try {
        final result = await Process.run(
          candidate.executable,
          [...candidate.prefixArgs, '--version'],
          runInShell: false,
        );
        if (result.exitCode == 0) return candidate;
      } on ProcessException {
        // Try next launcher.
      }
    }
    throw const MatchingBridgeException('python_not_found', 'Python was not found.');
  }
}

class _PythonCommand {
  const _PythonCommand(this.executable, {this.prefixArgs = const []});
  final String executable;
  final List<String> prefixArgs;
}

class MatchingBridgeException implements Exception {
  const MatchingBridgeException(this.code, this.message);
  final String code;
  final String message;
  @override
  String toString() => '$code: $message';
}

class FakeMatchingBridge implements MatchingBridgeClient {
  FakeMatchingBridge({this.ffmpegAvailable = true});

  final bool ffmpegAvailable;
  int runCalls = 0;
  int resultCalls = 0;
  int acceptCalls = 0;
  int rejectCalls = 0;
  int variantRunCalls = 0;
  int variantRunAllCalls = 0;

  final List<Map<String, dynamic>> _items = [
    {
      'providerId': 'yandex_music',
      'externalId': '201',
      'status': 'matched',
      'localFileId': 1,
      'confidence': 0.97,
      'method': 'title_artist_duration',
      'score': {'title': 1.0, 'artists': 1.0, 'duration': 0.95, 'album': 1.0, 'final': 0.97},
      'reason': 'auto_threshold_and_margin',
      'manual': false,
      'provider': {'title': 'Numb', 'artists': ['Linkin Park'], 'album_title': 'Meteora', 'duration_seconds': 185, 'explicit': false},
      'local': {'id': 1, 'title': 'Numb', 'artists': ['Linkin Park'], 'album': 'Meteora', 'durationSeconds': 185.4, 'path': r'C:\Music\Linkin Park\Numb.flac'},
    },
    {
      'providerId': 'yandex_music',
      'externalId': '202',
      'status': 'conflict',
      'localFileId': 2,
      'confidence': 0.91,
      'method': 'title_artist_duration',
      'score': {'title': 1.0, 'artists': 1.0, 'duration': 0.95, 'album': 0.6, 'final': 0.91},
      'reason': 'ambiguous_top_candidates',
      'manual': false,
      'provider': {'title': 'Song', 'artists': ['Artist A'], 'album_title': 'Album', 'duration_seconds': 200},
      'local': {'id': 2, 'title': 'Song', 'artists': ['Artist A'], 'album': 'Album', 'durationSeconds': 200.2, 'path': r'C:\Music\Song.flac'},
    },
    {
      'providerId': 'yandex_music',
      'externalId': '203',
      'status': 'unmatched',
      'localFileId': null,
      'confidence': 0.0,
      'method': 'automatic',
      'score': <String, dynamic>{},
      'reason': 'no_candidates',
      'manual': false,
      'provider': {'title': 'Missing Song', 'artists': ['Missing Artist'], 'album_title': 'Unknown', 'duration_seconds': 240},
      'local': null,
    },
  ];

  final Map<String, Map<String, dynamic>> variants = {
    '201': {
      'providerId': 'yandex_music',
      'externalId': '201',
      'localFileId': 1,
      'status': 'same',
      'variantStatus': 'same',
      'metadataScore': 1.0,
      'audioSimilarity': 0.98,
      'variantReasons': ['decoded_audio_consistent'],
      'alteredSegments': <Map<String, dynamic>>[],
      'referencePath': r'C:\MusicArk\.musicark\downloads\yandex\yandex_201.mp3',
      'metadata': {'providerMarkers': <String>[], 'localMarkers': <String>[]},
    },
  };

  List<Map<String, dynamic>> get _candidates => [
    {
      'conflictId': 10,
      'localFileId': 2,
      'confidence': 0.91,
      'score': {'title': 1.0, 'artists': 1.0, 'duration': 0.95, 'album': 0.6, 'final': 0.91},
      'reason': 'ambiguous_top_candidates',
      'status': 'open',
      'rank': 1,
      'local': {'title': 'Song', 'artists': ['Artist A'], 'album': 'Album', 'durationSeconds': 200.2, 'path': r'C:\Music\Song.flac', 'codec': 'flac'},
    },
    {
      'conflictId': 11,
      'localFileId': 3,
      'confidence': 0.90,
      'score': {'title': 1.0, 'artists': 1.0, 'duration': 0.9, 'album': 0.6, 'final': 0.90},
      'reason': 'ambiguous_top_candidates',
      'status': 'open',
      'rank': 2,
      'local': {'title': 'Song', 'artists': ['Artist A'], 'album': 'Single', 'durationSeconds': 201.0, 'path': r'C:\Music\Song.mp3', 'codec': 'mp3'},
    },
  ];

  @override
  Future<Map<String, dynamic>> matchingSummary() async {
    final matched = _items.where((item) => item['status'] == 'matched').length;
    final conflicts = _items.where((item) => item['status'] == 'conflict').length;
    final unmatched = _items.where((item) => item['status'] == 'unmatched').length;
    return {
      'providerId': 'yandex_music',
      'yandexTracks': _items.length,
      'localTracks': 4,
      'processed': _items.length,
      'matched': matched,
      'conflicts': conflicts,
      'unmatched': unmatched,
    };
  }

  @override
  Future<Map<String, dynamic>> matchingRun() async {
    runCalls++;
    final summary = await matchingSummary();
    return {
      'total': summary['processed'],
      'matched': summary['matched'],
      'conflicts': summary['conflicts'],
      'unmatched': summary['unmatched'],
      'unchanged': 0,
      'invalidated': 0,
      'indexUpdates': 0,
      'comparisons': 5,
      'durationSeconds': 0.01,
      'matcherVersion': 1,
      'summary': summary,
    };
  }

  @override
  Future<Map<String, dynamic>> matchingResults({
    int limit = 100,
    int offset = 0,
    String status = '',
    String search = '',
    String sort = 'confidence',
  }) async {
    resultCalls++;
    var items = List<Map<String, dynamic>>.from(_items);
    if (status.isNotEmpty) {
      items = items.where((item) => item['status'] == status).toList();
    }
    final query = search.trim().toLowerCase();
    if (query.isNotEmpty) {
      items = items.where((item) => jsonEncode(item).toLowerCase().contains(query)).toList();
    }
    if (sort == 'status') {
      items.sort((a, b) => '${a['status']}'.compareTo('${b['status']}'));
    } else if (sort == 'title') {
      items.sort((a, b) => '${(a['provider'] as Map)['title']}'.compareTo('${(b['provider'] as Map)['title']}'));
    } else {
      items.sort((a, b) => ((b['confidence'] as num?) ?? 0).compareTo((a['confidence'] as num?) ?? 0));
    }
    items = items.map((item) {
      final copy = Map<String, dynamic>.from(item);
      if (copy['status'] == 'matched' && copy['localFileId'] != null) {
        final externalId = '${copy['externalId']}';
        copy['variant'] = variants[externalId] ?? {
          'providerId': 'yandex_music',
          'externalId': externalId,
          'localFileId': copy['localFileId'],
          'status': 'not_checked',
          'variantStatus': 'not_checked',
          'variantReasons': ['audio_not_checked'],
          'alteredSegments': <Map<String, dynamic>>[],
          'audioSimilarity': null,
          'referencePath': null,
        };
      }
      return copy;
    }).toList();
    final total = items.length;
    final safeOffset = offset < 0 ? 0 : (offset > total ? total : offset);
    final requestedEnd = safeOffset + (limit < 0 ? 0 : limit);
    final safeEnd = requestedEnd > total ? total : requestedEnd;
    return {
      'count': total,
      'limit': limit,
      'offset': offset,
      'items': items.sublist(safeOffset, safeEnd),
    };
  }

  @override
  Future<Map<String, dynamic>> matchingResult(String externalId) async {
    final item = Map<String, dynamic>.from(
      _items.firstWhere((row) => row['externalId'] == externalId),
    );
    if (item['status'] == 'conflict') item['candidates'] = _candidates;
    return {'result': item};
  }

  @override
  Future<Map<String, dynamic>> matchingAccept(String externalId, int localFileId) async {
    acceptCalls++;
    final index = _items.indexWhere((row) => row['externalId'] == externalId);
    final candidate = _candidates.firstWhere((row) => row['localFileId'] == localFileId);
    final local = Map<String, dynamic>.from(candidate['local'] as Map);
    _items[index] = {
      ..._items[index],
      'status': 'matched',
      'localFileId': localFileId,
      'confidence': candidate['confidence'],
      'method': 'manual',
      'manual': true,
      'reason': 'manual_accept',
      'local': {'id': localFileId, ...local},
    };
    variants.remove(externalId);
    return matchingResult(externalId);
  }

  @override
  Future<Map<String, dynamic>> matchingReject(String externalId, int localFileId) async {
    rejectCalls++;
    final index = _items.indexWhere((row) => row['externalId'] == externalId);
    _items[index] = {
      ..._items[index],
      'status': 'unmatched',
      'localFileId': null,
      'confidence': 0.0,
      'method': 'automatic',
      'manual': false,
      'reason': 'manual_reject_no_candidates',
      'local': null,
    };
    variants.remove(externalId);
    return matchingResult(externalId);
  }

  @override
  Future<Map<String, dynamic>> variantCapabilities() async => {
    'providerId': 'yandex_music',
    'ffmpegAvailable': ffmpegAvailable,
    'audioVerificationAvailable': ffmpegAvailable,
    'sampleRate': 11025,
    'analyzerVersion': 1,
    'unavailableMessage': ffmpegAvailable ? null : 'Аудиосравнение недоступно: ffmpeg не найден',
  };

  @override
  Future<Map<String, dynamic>> variantSummary() async {
    final values = variants.values.toList();
    int count(String status) => values.where((item) => item['variantStatus'] == status).length;
    final matched = _items.where((item) => item['status'] == 'matched').length;
    return {
      'providerId': 'yandex_music',
      'eligibleMatched': matched,
      'stored': values.length,
      'checked': values.length,
      'same': count('same'),
      'altered': count('altered'),
      'differentVersion': count('different_version'),
      'uncertain': count('uncertain'),
      'notChecked': matched - values.length + count('not_checked'),
      'capabilities': await variantCapabilities(),
    };
  }

  @override
  Future<Map<String, dynamic>> variantRun(String externalId, {bool force = false}) async {
    variantRunCalls++;
    final localId = _items.firstWhere((row) => row['externalId'] == externalId)['localFileId'];
    variants[externalId] = {
      'providerId': 'yandex_music',
      'externalId': externalId,
      'localFileId': localId,
      'status': ffmpegAvailable ? 'same' : 'not_checked',
      'variantStatus': ffmpegAvailable ? 'same' : 'not_checked',
      'metadataScore': 1.0,
      'audioSimilarity': ffmpegAvailable ? 0.98 : null,
      'variantReasons': ffmpegAvailable ? ['decoded_audio_consistent'] : ['audio_decoder_unavailable'],
      'alteredSegments': <Map<String, dynamic>>[],
      'referencePath': r'C:\MusicArk\.musicark\downloads\yandex\yandex_201.mp3',
      'metadata': <String, dynamic>{},
    };
    return {'result': variants[externalId], 'cached': false, 'capabilities': await variantCapabilities()};
  }

  @override
  Future<Map<String, dynamic>> variantRunAllAvailable() async {
    variantRunAllCalls++;
    return {
      'eligibleMatched': _items.where((item) => item['status'] == 'matched').length,
      'available': 1,
      'processed': 1,
      'cached': 0,
      'errors': 0,
      'same': 1,
      'altered': 0,
      'differentVersion': 0,
      'uncertain': 0,
      'notChecked': 0,
      'progress': {'completed': 1, 'total': 1},
    };
  }

  @override
  Future<Map<String, dynamic>> variantResults({
    int limit = 500,
    int offset = 0,
    String status = '',
  }) async {
    var items = variants.values.map((item) => Map<String, dynamic>.from(item)).toList();
    if (status.isNotEmpty) {
      items = items.where((item) => item['variantStatus'] == status).toList();
    }
    final total = items.length;
    final safeOffset = offset.clamp(0, total).toInt();
    final safeEnd = (safeOffset + limit).clamp(safeOffset, total).toInt();
    return {
      'count': total,
      'limit': limit,
      'offset': offset,
      'items': items.sublist(safeOffset, safeEnd),
    };
  }

  @override
  Future<Map<String, dynamic>> variantResult(String externalId) async {
    final existing = variants[externalId];
    if (existing != null) return {'result': Map<String, dynamic>.from(existing)};
    final row = _items.firstWhere((item) => item['externalId'] == externalId);
    if (row['status'] != 'matched') {
      throw const MatchingBridgeException('invalid_request', 'Variant analysis requires a MATCHED identity.');
    }
    return {
      'result': {
        'providerId': 'yandex_music',
        'externalId': externalId,
        'localFileId': row['localFileId'],
        'status': 'not_checked',
        'variantStatus': 'not_checked',
        'metadataScore': null,
        'audioSimilarity': null,
        'variantReasons': ['audio_not_checked'],
        'alteredSegments': <Map<String, dynamic>>[],
        'referencePath': null,
        'metadata': <String, dynamic>{},
      },
    };
  }
}
