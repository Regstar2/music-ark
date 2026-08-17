import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';
export 'musicark_bridge.dart';

abstract interface class ContentLabelBridgeClient {
  Future<Map<String, dynamic>> batch({
    List<int> localFileIds = const [],
    List<String> externalIds = const [],
    String providerId = 'yandex_music',
  });
  Future<Map<String, dynamic>> setLocal(int localFileId, String label);
  Future<Map<String, dynamic>> setProvider(
    String externalId,
    String label, {
    String providerId = 'yandex_music',
  });
}

class ContentLabelBridge implements ContentLabelBridgeClient {
  const ContentLabelBridge();

  @override
  Future<Map<String, dynamic>> batch({
    List<int> localFileIds = const [],
    List<String> externalIds = const [],
    String providerId = 'yandex_music',
  }) =>
      _run(
        'batch',
        providerId: providerId,
        payload: {
          'localFileIds': localFileIds,
          'externalIds': externalIds,
        },
      );

  @override
  Future<Map<String, dynamic>> setLocal(int localFileId, String label) =>
      _run('set_local', localFileId: localFileId, label: label);

  @override
  Future<Map<String, dynamic>> setProvider(
    String externalId,
    String label, {
    String providerId = 'yandex_music',
  }) =>
      _run(
        'set_provider',
        providerId: providerId,
        externalId: externalId,
        label: label,
      );

  Future<Map<String, dynamic>> _run(
    String command, {
    int? localFileId,
    String providerId = 'yandex_music',
    String? externalId,
    String? label,
    Map<String, dynamic>? payload,
  }) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePython(repoRoot);
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
    environment.remove('MUSICARK_CONTENT_LABEL_PAYLOAD');
    if (payload != null) {
      environment['MUSICARK_CONTENT_LABEL_PAYLOAD'] = jsonEncode(payload);
    }
    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.content_labels.bridge',
      '--base-dir',
      repoRoot,
      command,
      '--provider-id',
      providerId,
      if (localFileId != null) ...['--local-file-id', '$localFileId'],
      if (externalId != null && externalId.isNotEmpty) ...['--external-id', externalId],
      if (label != null) ...['--label', label],
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
    Map<String, dynamic>? decoded;
    if (stdoutText.isNotEmpty) {
      try {
        final value = jsonDecode(stdoutText);
        if (value is Map) decoded = Map<String, dynamic>.from(value);
      } on FormatException {
        decoded = null;
      }
    }
    final rawError = decoded?['error'];
    if (rawError is Map) {
      final error = Map<String, dynamic>.from(rawError);
      throw MusicArkBridgeException(
        '${error['code'] ?? 'unexpected_error'}',
        '${error['message'] ?? stderrText}',
      );
    }
    if (result.exitCode != 0 || decoded == null) {
      throw MusicArkBridgeException(
        'unexpected_error',
        stderrText.isNotEmpty
            ? stderrText
            : (stdoutText.isNotEmpty
                ? stdoutText
                : 'Content label bridge returned invalid JSON.'),
      );
    }
    return decoded;
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
      'MusicArk repository root was not found.',
    );
  }

  bool _looksLikeRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File('${directory.path}${separator}src${separator}musicark${separator}content_labels${separator}bridge.py').existsSync();
  }

  Future<_ContentLabelPythonCommand> _resolvePython(String repoRoot) async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) {
      final command = _ContentLabelPythonCommand(override);
      if (await _works(command)) return command;
    }
    final separator = Platform.pathSeparator;
    final venv = Platform.isWindows
        ? '$repoRoot${separator}.venv${separator}Scripts${separator}python.exe'
        : '$repoRoot${separator}.venv${separator}bin${separator}python';
    if (File(venv).existsSync()) {
      final command = _ContentLabelPythonCommand(venv);
      if (await _works(command)) return command;
    }
    final candidates = Platform.isWindows
        ? const [
            _ContentLabelPythonCommand('python'),
            _ContentLabelPythonCommand('py', prefixArgs: ['-3']),
          ]
        : const [
            _ContentLabelPythonCommand('python3'),
            _ContentLabelPythonCommand('python'),
          ];
    for (final command in candidates) {
      if (await _works(command)) return command;
    }
    throw const MusicArkBridgeException('python_not_found', 'Python was not found.');
  }

  Future<bool> _works(_ContentLabelPythonCommand command) async {
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

class _ContentLabelPythonCommand {
  const _ContentLabelPythonCommand(this.executable, {this.prefixArgs = const []});
  final String executable;
  final List<String> prefixArgs;
}

class FakeContentLabelBridge implements ContentLabelBridgeClient {
  final Map<int, String> localLabels = {};
  final Map<String, String> providerLabels = {};

  @override
  Future<Map<String, dynamic>> batch({
    List<int> localFileIds = const [],
    List<String> externalIds = const [],
    String providerId = 'yandex_music',
  }) async =>
      {
        'local': {
          for (final id in localFileIds)
            if (localLabels[id] != null) '$id': localLabels[id],
        },
        'provider': {
          for (final id in externalIds)
            if (providerLabels[id] != null) id: providerLabels[id],
        },
        'providerId': providerId,
      };

  @override
  Future<Map<String, dynamic>> setLocal(int localFileId, String label) async {
    if (label.isEmpty) {
      localLabels.remove(localFileId);
    } else {
      localLabels[localFileId] = label;
    }
    return {'subject': 'local', 'localFileId': localFileId, 'label': label.isEmpty ? null : label};
  }

  @override
  Future<Map<String, dynamic>> setProvider(
    String externalId,
    String label, {
    String providerId = 'yandex_music',
  }) async {
    if (label.isEmpty) {
      providerLabels.remove(externalId);
    } else {
      providerLabels[externalId] = label;
    }
    return {
      'subject': 'provider',
      'providerId': providerId,
      'externalId': externalId,
      'label': label.isEmpty ? null : label,
    };
  }
}
