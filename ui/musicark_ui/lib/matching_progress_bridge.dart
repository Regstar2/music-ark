import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import 'matching_bridge.dart';

class MatchingRunProgress {
  const MatchingRunProgress({
    required this.running,
    required this.processed,
    required this.total,
  });

  const MatchingRunProgress.idle()
      : running = false,
        processed = 0,
        total = 0;

  final bool running;
  final int processed;
  final int total;

  double? get fraction {
    if (total <= 0) return null;
    return (processed / total).clamp(0.0, 1.0).toDouble();
  }
}

abstract interface class MatchingProgressSource {
  ValueListenable<MatchingRunProgress> get matchingProgress;
}

/// Production matching bridge with cached runtime discovery and streamed progress.
///
/// The legacy [MatchingBridge] remains available for focused tests and compatibility;
/// the desktop composition root uses this implementation for release builds.
class ResponsiveMatchingBridge
    implements MatchingBridgeClient, MatchingProgressSource {
  static const _progressPrefix = '__MUSICARK_MATCHING_PROGRESS__';

  final ValueNotifier<MatchingRunProgress> _matchingProgress =
      ValueNotifier<MatchingRunProgress>(const MatchingRunProgress.idle());
  String? _cachedRepoRoot;
  Future<_PythonCommand>? _pythonCommandFuture;

  @override
  ValueListenable<MatchingRunProgress> get matchingProgress => _matchingProgress;

  @override
  Future<Map<String, dynamic>> matchingSummary() => _run('matching_summary');

  @override
  Future<Map<String, dynamic>> matchingRun() =>
      _run('matching_run', streamMatchingProgress: true);

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
  Future<Map<String, dynamic>> matchingAccept(
    String externalId,
    int localFileId,
  ) =>
      _run(
        'matching_accept',
        externalId: externalId,
        localFileId: localFileId,
      );

  @override
  Future<Map<String, dynamic>> matchingReject(
    String externalId,
    int localFileId,
  ) =>
      _run(
        'matching_reject',
        externalId: externalId,
        localFileId: localFileId,
      );

  @override
  Future<Map<String, dynamic>> variantCapabilities() =>
      _run('variant_capabilities');

  @override
  Future<Map<String, dynamic>> variantSummary() => _run('variant_summary');

  @override
  Future<Map<String, dynamic>> variantRun(
    String externalId, {
    bool force = false,
  }) =>
      _run('variant_run', externalId: externalId, force: force);

  @override
  Future<Map<String, dynamic>> variantRunAllAvailable() =>
      _run('variant_run_all_available');

  @override
  Future<Map<String, dynamic>> variantResults({
    int limit = 500,
    int offset = 0,
    String status = '',
  }) =>
      _run('variant_results', limit: limit, offset: offset, status: status);

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
    bool streamMatchingProgress = false,
  }) async {
    final repoRoot = _cachedRepoRoot ??= _resolveRepoRoot();
    final python = await _cachedPythonCommand(repoRoot);
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

    final module = streamMatchingProgress
        ? 'musicark.matching.progress_bridge'
        : 'musicark.mvp_bridge';
    final args = <String>[
      ...python.prefixArgs,
      '-m',
      module,
      '--base-dir',
      repoRoot,
      command,
      if (externalId != null && externalId.isNotEmpty) ...[
        '--external-id',
        externalId,
      ],
      if (localFileId != null) ...['--local-file-id', '$localFileId'],
      if (limit != null) ...['--limit', '$limit'],
      if (offset != null) ...['--offset', '$offset'],
      if (status != null && status.isNotEmpty) ...['--status', status],
      if (search != null && search.isNotEmpty) ...['--search', search],
      if (sort != null && sort.isNotEmpty) ...['--sort', sort],
      if (force) '--force',
    ];

    if (streamMatchingProgress) {
      return _runMatchingProcess(
        python: python,
        args: args,
        repoRoot: repoRoot,
        environment: environment,
      );
    }

    final result = await Process.run(
      python.executable,
      args,
      runInShell: false,
      workingDirectory: repoRoot,
      environment: environment,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    return _decodeResult(
      exitCode: result.exitCode,
      stdoutText: (result.stdout ?? '').toString().trim(),
      stderrText: (result.stderr ?? '').toString().trim(),
    );
  }

  Future<Map<String, dynamic>> _runMatchingProcess({
    required _PythonCommand python,
    required List<String> args,
    required String repoRoot,
    required Map<String, String> environment,
  }) async {
    _matchingProgress.value = const MatchingRunProgress(
      running: true,
      processed: 0,
      total: 0,
    );
    try {
      final process = await Process.start(
        python.executable,
        args,
        runInShell: false,
        workingDirectory: repoRoot,
        environment: environment,
      );
      final stderrBuffer = StringBuffer();
      final stdoutFuture = process.stdout.transform(utf8.decoder).join();
      final stderrFuture = process.stderr
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .forEach((line) {
        if (line.startsWith(_progressPrefix)) {
          final raw = line.substring(_progressPrefix.length);
          try {
            final decoded = jsonDecode(raw);
            if (decoded is Map) {
              final processed =
                  int.tryParse('${decoded['processed'] ?? 0}') ?? 0;
              final total = int.tryParse('${decoded['total'] ?? 0}') ?? 0;
              _matchingProgress.value = MatchingRunProgress(
                running: true,
                processed: processed,
                total: total,
              );
              return;
            }
          } on FormatException {
            // Preserve malformed diagnostics without interrupting the run.
          }
        }
        if (stderrBuffer.isNotEmpty) stderrBuffer.writeln();
        stderrBuffer.write(line);
      });

      final exitCode = await process.exitCode;
      final stdoutText = (await stdoutFuture).trim();
      await stderrFuture;
      final payload = _decodeResult(
        exitCode: exitCode,
        stdoutText: stdoutText,
        stderrText: stderrBuffer.toString().trim(),
      );
      final finalTotal = int.tryParse(
            '${payload['providerIdentities'] ?? payload['total'] ?? 0}',
          ) ??
          0;
      if (finalTotal > 0) {
        _matchingProgress.value = MatchingRunProgress(
          running: true,
          processed: finalTotal,
          total: finalTotal,
        );
      }
      return payload;
    } finally {
      final current = _matchingProgress.value;
      _matchingProgress.value = MatchingRunProgress(
        running: false,
        processed: current.processed,
        total: current.total,
      );
    }
  }

  Map<String, dynamic> _decodeResult({
    required int exitCode,
    required String stdoutText,
    required String stderrText,
  }) {
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
    if (exitCode != 0 || payload == null) {
      throw MatchingBridgeException(
        'unexpected_error',
        stderrText.isNotEmpty ? stderrText : stdoutText,
      );
    }
    return payload;
  }

  Future<_PythonCommand> _cachedPythonCommand(String repoRoot) async {
    final existing = _pythonCommandFuture;
    if (existing != null) return existing;
    final resolving = _resolvePythonCommand(repoRoot);
    _pythonCommandFuture = resolving;
    try {
      return await resolving;
    } catch (_) {
      if (identical(_pythonCommandFuture, resolving)) {
        _pythonCommandFuture = null;
      }
      rethrow;
    }
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
    return File(
          '${directory.path}${separator}pyproject.toml',
        ).existsSync() &&
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
        ? const [
            _PythonCommand('python'),
            _PythonCommand('py', prefixArgs: ['-3']),
          ]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final candidate in candidates) {
      if (await _pythonWorks(candidate)) return candidate;
    }
    throw const MatchingBridgeException(
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
