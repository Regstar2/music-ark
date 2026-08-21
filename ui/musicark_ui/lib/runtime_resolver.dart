import 'dart:io';

/// One resolved Python process environment for every MusicArk desktop bridge.
///
/// Resolution order is deliberately stable:
/// 1. explicit development/test override;
/// 2. bundled runtime beside the installed Flutter executable;
/// 3. repository .venv;
/// 4. system Python for development only.
///
/// Installed builds never need a repository checkout and store mutable state
/// outside the installation directory.
class MusicArkRuntime {
  const MusicArkRuntime({
    required this.pythonExecutable,
    required this.pythonPrefixArgs,
    required this.workingDirectory,
    required this.dataBaseDir,
    required this.packaged,
    this.repositoryRoot,
  });

  final String pythonExecutable;
  final List<String> pythonPrefixArgs;
  final String workingDirectory;
  final String dataBaseDir;
  final bool packaged;
  final String? repositoryRoot;

  Map<String, String> environment({Map<String, String> extra = const {}}) {
    final result = <String, String>{
      ...Platform.environment,
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
      'MUSICARK_DATA_ROOT': dataBaseDir,
      ...extra,
    };
    final repo = repositoryRoot;
    if (!packaged && repo != null) {
      final src = _join(repo, 'src');
      final existing = result['PYTHONPATH'];
      result['PYTHONPATH'] = existing == null || existing.isEmpty
          ? src
          : '$src${Platform.isWindows ? ';' : ':'}$existing';
    } else {
      // A packaged runtime imports MusicArk from Lib/site-packages. Do not let a
      // developer/user PYTHONPATH redirect an installed application to another
      // checkout.
      result.remove('PYTHONPATH');
    }
    return result;
  }

  static String _join(String left, String right) =>
      '$left${Platform.pathSeparator}$right';
}

class MusicArkRuntimeResolver {
  MusicArkRuntimeResolver({Map<String, String>? environment})
      : _environment = environment ?? Platform.environment;

  final Map<String, String> _environment;
  Future<MusicArkRuntime>? _cached;

  Future<MusicArkRuntime> resolve() => _cached ??= _resolve();

  Future<MusicArkRuntime> _resolve() async {
    final explicitPython = _clean(_environment['MUSICARK_PYTHON']);
    final explicitRepo = _clean(_environment['MUSICARK_REPO_ROOT']);
    if (explicitPython != null) {
      final command = _PythonCommand(explicitPython);
      if (!await _works(command)) {
        throw const MusicArkRuntimeException(
          'python_override_invalid',
          'MUSICARK_PYTHON does not point to a working Python executable.',
        );
      }
      final repo = explicitRepo == null ? _findRepositoryRoot() : _validRepo(explicitRepo);
      if (repo == null) {
        throw const MusicArkRuntimeException(
          'repo_root_not_found',
          'A repository root is required when MUSICARK_PYTHON is used for development.',
        );
      }
      return _developmentRuntime(command, repo);
    }

    final executableDir = File(Platform.resolvedExecutable).parent.absolute.path;
    final packagedPython = _joinAll([
      executableDir,
      'runtime',
      'python',
      Platform.isWindows ? 'python.exe' : 'python',
    ]);
    if (File(packagedPython).isFileSync()) {
      final command = _PythonCommand(packagedPython);
      if (!await _works(command)) {
        throw const MusicArkRuntimeException(
          'packaged_runtime_invalid',
          'The bundled MusicArk runtime is present but cannot be started.',
        );
      }
      return MusicArkRuntime(
        pythonExecutable: packagedPython,
        pythonPrefixArgs: const [],
        workingDirectory: executableDir,
        dataBaseDir: _resolveDataBaseDir(),
        packaged: true,
      );
    }

    final repo = explicitRepo == null ? _findRepositoryRoot() : _validRepo(explicitRepo);
    if (repo != null) {
      final venv = Platform.isWindows
          ? _joinAll([repo, '.venv', 'Scripts', 'python.exe'])
          : _joinAll([repo, '.venv', 'bin', 'python']);
      if (File(venv).isFileSync()) {
        final command = _PythonCommand(venv);
        if (await _works(command)) return _developmentRuntime(command, repo);
      }

      final candidates = Platform.isWindows
          ? const [
              _PythonCommand('python'),
              _PythonCommand('py', prefixArgs: ['-3']),
            ]
          : const [_PythonCommand('python3'), _PythonCommand('python')];
      for (final command in candidates) {
        if (await _works(command)) return _developmentRuntime(command, repo);
      }
    }

    throw const MusicArkRuntimeException(
      'python_not_found',
      'MusicArk could not find its bundled runtime or a development Python environment.',
    );
  }

  MusicArkRuntime _developmentRuntime(_PythonCommand command, String repo) =>
      MusicArkRuntime(
        pythonExecutable: command.executable,
        pythonPrefixArgs: command.prefixArgs,
        workingDirectory: repo,
        dataBaseDir: _resolveDataBaseDir(developmentRepo: repo),
        packaged: false,
        repositoryRoot: repo,
      );

  String _resolveDataBaseDir({String? developmentRepo}) {
    final override = _clean(_environment['MUSICARK_DATA_ROOT']);
    if (override != null) return Directory(override).absolute.path;
    if (developmentRepo != null) return developmentRepo;
    if (Platform.isWindows) {
      final localAppData = _clean(_environment['LOCALAPPDATA']);
      if (localAppData != null) return _joinAll([localAppData, 'MusicArk']);
    }
    final home = _clean(_environment[Platform.isWindows ? 'USERPROFILE' : 'HOME']);
    if (home != null) return _joinAll([home, '.musicark-data']);
    return Directory.systemTemp.createTempSync('musicark-data-').path;
  }

  String? _findRepositoryRoot() {
    final starts = <Directory>{
      Directory.current.absolute,
      File(Platform.resolvedExecutable).parent.absolute,
    };
    for (final start in starts) {
      var current = start;
      while (true) {
        if (_looksLikeRepository(current)) return current.path;
        final parent = current.parent;
        if (parent.path == current.path) break;
        current = parent;
      }
    }
    return null;
  }

  String? _validRepo(String value) {
    final directory = Directory(value).absolute;
    return _looksLikeRepository(directory) ? directory.path : null;
  }

  bool _looksLikeRepository(Directory directory) {
    return File(_joinAll([directory.path, 'pyproject.toml'])).isFileSync() &&
        File(_joinAll([directory.path, 'src', 'musicark', '__init__.py'])).isFileSync();
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

  static String? _clean(String? value) {
    final result = value?.trim();
    return result == null || result.isEmpty ? null : result;
  }

  static String _joinAll(List<String> parts) => parts.join(Platform.pathSeparator);
}

class MusicArkRuntimeException implements Exception {
  const MusicArkRuntimeException(this.code, this.message);
  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}

class _PythonCommand {
  const _PythonCommand(this.executable, {this.prefixArgs = const []});
  final String executable;
  final List<String> prefixArgs;
}
