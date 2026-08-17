import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';

abstract interface class VariantAcceptanceBridgeClient {
  Future<Map<String, dynamic>> get(String externalId, int localFileId);
  Future<Map<String, dynamic>> accept(String externalId, int localFileId);
  Future<Map<String, dynamic>> reset(String externalId, int localFileId);
}

class VariantAcceptanceBridge implements VariantAcceptanceBridgeClient {
  const VariantAcceptanceBridge();

  @override
  Future<Map<String, dynamic>> get(String externalId, int localFileId) =>
      _run('get', externalId, localFileId);

  @override
  Future<Map<String, dynamic>> accept(String externalId, int localFileId) =>
      _run('accept', externalId, localFileId);

  @override
  Future<Map<String, dynamic>> reset(String externalId, int localFileId) =>
      _run('reset', externalId, localFileId);

  Future<Map<String, dynamic>> _run(
    String command,
    String externalId,
    int localFileId,
  ) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePython(repoRoot);
    final separator = Platform.pathSeparator;
    final srcPath = '$repoRoot${separator}src';
    final existing = Platform.environment['PYTHONPATH'];
    final environment = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': existing == null || existing.isEmpty
          ? srcPath
          : '$srcPath${Platform.isWindows ? ';' : ':'}$existing',
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    }..remove('YANDEX_MUSIC_TOKEN');
    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.variant.acceptance_bridge',
      '--base-dir',
      repoRoot,
      command,
      '--external-id',
      externalId,
      '--local-file-id',
      '$localFileId',
    ];
    final result = await Process.run(
      python.executable,
      args,
      workingDirectory: repoRoot,
      runInShell: false,
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
      throw MusicArkBridgeException(
        '${error['code'] ?? 'unexpected_error'}',
        '${error['message'] ?? stderrText}',
      );
    }
    if (result.exitCode != 0 || payload == null) {
      throw MusicArkBridgeException(
        'unexpected_error',
        stderrText.isNotEmpty
            ? stderrText
            : (stdoutText.isNotEmpty
                ? stdoutText
                : 'Variant acceptance bridge returned invalid JSON.'),
      );
    }
    return payload;
  }

  String _resolveRepoRoot() {
    final override = Platform.environment['MUSICARK_REPO_ROOT']?.trim();
    if (override != null && override.isNotEmpty && _looksLikeRoot(Directory(override))) {
      return Directory(override).absolute.path;
    }
    final starts = <Directory>{
      Directory.current.absolute,
      File(Platform.resolvedExecutable).parent.absolute,
    };
    for (final start in starts) {
      var current = start;
      while (true) {
        if (_looksLikeRoot(current)) return current.path;
        final parent = current.parent;
        if (parent.path == current.path) break;
        current = parent;
      }
    }
    throw const MusicArkBridgeException(
      'repo_root_not_found',
      'Корневая папка репозитория MusicArk не найдена.',
    );
  }

  bool _looksLikeRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File('${directory.path}${separator}src${separator}musicark${separator}variant${separator}acceptance_bridge.py').existsSync();
  }

  Future<_PythonCommand> _resolvePython(String repoRoot) async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) {
      final command = _PythonCommand(override);
      if (await _works(command)) return command;
    }
    final separator = Platform.pathSeparator;
    final venv = Platform.isWindows
        ? '$repoRoot${separator}.venv${separator}Scripts${separator}python.exe'
        : '$repoRoot${separator}.venv${separator}bin${separator}python';
    if (File(venv).existsSync()) {
      final command = _PythonCommand(venv);
      if (await _works(command)) return command;
    }
    final candidates = Platform.isWindows
        ? const [_PythonCommand('python'), _PythonCommand('py', prefixArgs: ['-3'])]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final candidate in candidates) {
      if (await _works(candidate)) return candidate;
    }
    throw const MusicArkBridgeException('python_not_found', 'Python не найден.');
  }

  Future<bool> _works(_PythonCommand command) async {
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

class FakeVariantAcceptanceBridge implements VariantAcceptanceBridgeClient {
  final Map<String, bool> accepted = {};
  int acceptCalls = 0;
  int resetCalls = 0;

  String _key(String externalId, int localFileId) => '$externalId:$localFileId';

  @override
  Future<Map<String, dynamic>> get(String externalId, int localFileId) async => {
        'externalId': externalId,
        'localFileId': localFileId,
        'accepted': accepted[_key(externalId, localFileId)] == true,
      };

  @override
  Future<Map<String, dynamic>> accept(String externalId, int localFileId) async {
    acceptCalls++;
    accepted[_key(externalId, localFileId)] = true;
    return get(externalId, localFileId);
  }

  @override
  Future<Map<String, dynamic>> reset(String externalId, int localFileId) async {
    resetCalls++;
    accepted.remove(_key(externalId, localFileId));
    return get(externalId, localFileId);
  }
}
