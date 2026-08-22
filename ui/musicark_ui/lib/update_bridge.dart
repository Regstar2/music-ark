import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';
import 'runtime_resolver.dart';

const _updatePayloadEnv = 'MUSICARK_UPDATE_PAYLOAD';

abstract interface class UpdateBridgeClient {
  Future<Map<String, dynamic>> check();
  Future<Map<String, dynamic>> prepare();
  Future<Map<String, dynamic>> apply(String version, {required bool confirm});
}

class UpdateBridge implements UpdateBridgeClient {
  UpdateBridge({MusicArkRuntimeResolver? runtimeResolver})
      : _runtimeResolver = runtimeResolver ?? MusicArkRuntimeResolver();

  final MusicArkRuntimeResolver _runtimeResolver;

  @override
  Future<Map<String, dynamic>> check() => _run('check');

  @override
  Future<Map<String, dynamic>> prepare() => _run('prepare');

  @override
  Future<Map<String, dynamic>> apply(String version, {required bool confirm}) =>
      _run('apply', payload: {'version': version, 'confirm': confirm});

  Future<Map<String, dynamic>> _run(
    String command, {
    Map<String, dynamic>? payload,
  }) async {
    final runtime = await _runtimeResolver.resolve();
    Directory(runtime.dataBaseDir).createSync(recursive: true);
    final environment = runtime.environment(
      extra: {
        if (payload != null) _updatePayloadEnv: jsonEncode(payload),
      },
    );
    environment.remove('YANDEX_MUSIC_TOKEN');
    final result = await Process.run(
      runtime.pythonExecutable,
      [
        ...runtime.pythonPrefixArgs,
        '-m',
        'musicark.update.bridge',
        '--base-dir',
        runtime.dataBaseDir,
        command,
      ],
      runInShell: false,
      workingDirectory: runtime.workingDirectory,
      environment: environment,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    final stdout = '${result.stdout ?? ''}'.trim();
    final stderr = '${result.stderr ?? ''}'.trim();
    Map<String, dynamic>? decoded;
    if (stdout.isNotEmpty) {
      try {
        final value = jsonDecode(stdout);
        if (value is Map) decoded = Map<String, dynamic>.from(value);
      } on FormatException {
        decoded = null;
      }
    }
    final rawError = decoded?['error'];
    if (rawError is Map) {
      final error = Map<String, dynamic>.from(rawError);
      throw MusicArkBridgeException(
        '${error['code'] ?? 'update_failed'}',
        '${error['message'] ?? stderr}',
      );
    }
    if (result.exitCode != 0 || decoded == null) {
      throw MusicArkBridgeException(
        'update_failed',
        stderr.isNotEmpty ? stderr : 'MusicArk update bridge returned invalid JSON.',
      );
    }
    return decoded;
  }
}

class FakeUpdateBridge implements UpdateBridgeClient {
  FakeUpdateBridge({
    this.currentVersion = '0.15.0',
    this.latestVersion = '0.15.0',
    this.failCheck = false,
  });

  String currentVersion;
  String latestVersion;
  bool failCheck;
  int checkCalls = 0;
  int prepareCalls = 0;
  int applyCalls = 0;

  bool get available => _compare(latestVersion, currentVersion) > 0;

  @override
  Future<Map<String, dynamic>> check() async {
    checkCalls += 1;
    if (failCheck) {
      throw const MusicArkBridgeException('network_failed', 'Update server unavailable.');
    }
    return {
      'currentVersion': currentVersion,
      'channel': 'stable',
      'available': available,
      'latest': {
        'schemaVersion': 1,
        'channel': 'stable',
        'version': latestVersion,
        'publishedAt': '2026-08-22T00:00:00Z',
        'releaseNotesUrl': null,
      },
    };
  }

  @override
  Future<Map<String, dynamic>> prepare() async {
    prepareCalls += 1;
    return {
      'available': available,
      'version': latestVersion,
      'fileName': 'MusicArk-Setup-$latestVersion.exe',
      'sha256': '0' * 64,
      'sizeBytes': 1024,
      'cached': false,
    };
  }

  @override
  Future<Map<String, dynamic>> apply(String version, {required bool confirm}) async {
    applyCalls += 1;
    if (!confirm) {
      throw const MusicArkBridgeException('installer_launch_failed', 'Confirmation required.');
    }
    return {'launched': true, 'version': version, 'pid': 1};
  }

  static int _compare(String left, String right) {
    final a = left.split('.').map(int.parse).toList();
    final b = right.split('.').map(int.parse).toList();
    for (var i = 0; i < 3; i += 1) {
      if (a[i] != b[i]) return a[i].compareTo(b[i]);
    }
    return 0;
  }
}
