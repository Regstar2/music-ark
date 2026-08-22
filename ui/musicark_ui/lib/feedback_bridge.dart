import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';
import 'runtime_resolver.dart';

abstract interface class FeedbackBridgeClient {
  Future<Map<String, dynamic>> link(String kind);
  Future<Map<String, dynamic>> open(String kind);
}

class FeedbackBridge implements FeedbackBridgeClient {
  FeedbackBridge({MusicArkRuntimeResolver? runtimeResolver})
      : _runtimeResolver = runtimeResolver ?? MusicArkRuntimeResolver();

  final MusicArkRuntimeResolver _runtimeResolver;

  @override
  Future<Map<String, dynamic>> link(String kind) => _run('link', kind);

  @override
  Future<Map<String, dynamic>> open(String kind) => _run('open', kind);

  Future<Map<String, dynamic>> _run(String command, String kind) async {
    final runtime = await _runtimeResolver.resolve();
    Directory(runtime.dataBaseDir).createSync(recursive: true);
    final environment = runtime.environment();
    environment.remove('YANDEX_MUSIC_TOKEN');
    final result = await Process.run(
      runtime.pythonExecutable,
      [
        ...runtime.pythonPrefixArgs,
        '-m',
        'musicark.feedback_bridge',
        command,
        '--kind',
        kind,
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
    if (decoded?['error'] is Map) {
      final error = Map<String, dynamic>.from(decoded!['error'] as Map);
      throw MusicArkBridgeException(
        '${error['code'] ?? 'feedback_failed'}',
        '${error['message'] ?? stderr}',
      );
    }
    if (result.exitCode != 0 || decoded == null) {
      throw MusicArkBridgeException(
        'feedback_failed',
        stderr.isNotEmpty ? stderr : 'MusicArk feedback bridge returned invalid JSON.',
      );
    }
    return decoded;
  }
}

class FakeFeedbackBridge implements FeedbackBridgeClient {
  int bugOpenCalls = 0;
  int featureOpenCalls = 0;

  @override
  Future<Map<String, dynamic>> link(String kind) async => {
        'kind': kind,
        'url': 'https://github.com/Regstar2/music-ark/issues/new?template=$kind',
      };

  @override
  Future<Map<String, dynamic>> open(String kind) async {
    if (kind == 'bug') bugOpenCalls += 1;
    if (kind == 'feature') featureOpenCalls += 1;
    return {
      'opened': true,
      'kind': kind,
      'url': 'https://github.com/Regstar2/music-ark/issues/new?template=$kind',
    };
  }
}
