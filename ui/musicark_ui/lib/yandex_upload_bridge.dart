import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';

enum YandexUploadStatus {
  verified,
  processing,
  deliveryUnknown,
  stage1Failed,
  stage2HttpFailed,
  preflightFailed,
  unsupportedFormat,
  ambiguous,
}

class YandexUploadTarget {
  const YandexUploadTarget({
    required this.playlistKind,
    required this.title,
    required this.trackCount,
  });

  final String playlistKind;
  final String title;
  final int trackCount;

  factory YandexUploadTarget.fromJson(Map<String, dynamic> json) =>
      YandexUploadTarget(
        playlistKind: '${json['playlistKind'] ?? ''}',
        title: '${json['title'] ?? ''}',
        trackCount: int.tryParse('${json['trackCount'] ?? 0}') ?? 0,
      );
}

class YandexUploadTargets {
  const YandexUploadTargets({
    required this.authenticated,
    required this.playlists,
  });

  final bool authenticated;
  final List<YandexUploadTarget> playlists;

  factory YandexUploadTargets.fromJson(Map<String, dynamic> json) {
    final raw = json['playlists'];
    final playlists = raw is List
        ? raw
              .whereType<Map>()
              .map(
                (item) => YandexUploadTarget.fromJson(
                  Map<String, dynamic>.from(item),
                ),
              )
              .where((item) => item.playlistKind.isNotEmpty)
              .toList(growable: false)
        : <YandexUploadTarget>[];
    return YandexUploadTargets(
      authenticated: json['authenticated'] == true,
      playlists: playlists,
    );
  }
}

class YandexUploadResult {
  const YandexUploadResult({
    required this.status,
    required this.localFileId,
    required this.playlistKind,
    this.trackId,
    this.stage1HttpStatus,
    this.stage2HttpStatus,
    required this.readBackVerified,
    required this.readBackAttempts,
    this.errorCode,
    required this.safeMessage,
  });

  final YandexUploadStatus status;
  final int localFileId;
  final String playlistKind;
  final String? trackId;
  final int? stage1HttpStatus;
  final int? stage2HttpStatus;
  final bool readBackVerified;
  final int readBackAttempts;
  final String? errorCode;
  final String safeMessage;

  static YandexUploadStatus _status(String value) => switch (value) {
    'verified' => YandexUploadStatus.verified,
    'processing' => YandexUploadStatus.processing,
    'delivery_unknown' => YandexUploadStatus.deliveryUnknown,
    'stage1_failed' => YandexUploadStatus.stage1Failed,
    'stage2_http_failed' => YandexUploadStatus.stage2HttpFailed,
    'preflight_failed' => YandexUploadStatus.preflightFailed,
    'unsupported_format' => YandexUploadStatus.unsupportedFormat,
    'ambiguous' => YandexUploadStatus.ambiguous,
    _ => YandexUploadStatus.preflightFailed,
  };

  factory YandexUploadResult.fromJson(Map<String, dynamic> json) =>
      YandexUploadResult(
        status: _status('${json['status'] ?? ''}'),
        localFileId: int.tryParse('${json['localFileId'] ?? 0}') ?? 0,
        playlistKind: '${json['playlistKind'] ?? ''}',
        trackId: json['trackId'] == null ? null : '${json['trackId']}',
        stage1HttpStatus: json['stage1HttpStatus'] == null
            ? null
            : int.tryParse('${json['stage1HttpStatus']}'),
        stage2HttpStatus: json['stage2HttpStatus'] == null
            ? null
            : int.tryParse('${json['stage2HttpStatus']}'),
        readBackVerified: json['readBackVerified'] == true,
        readBackAttempts: int.tryParse('${json['readBackAttempts'] ?? 0}') ?? 0,
        errorCode: json['errorCode'] == null ? null : '${json['errorCode']}',
        safeMessage: '${json['safeMessage'] ?? ''}',
      );
}

abstract interface class YandexUploadBridgeClient {
  Future<YandexUploadTargets> targets();

  Future<YandexUploadResult> uploadTrack({
    required int localFileId,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
  });
}

class YandexUploadBridge implements YandexUploadBridgeClient {
  const YandexUploadBridge();

  static const _payloadEnv = 'MUSICARK_YANDEX_UPLOAD_PAYLOAD';

  @override
  Future<YandexUploadTargets> targets() async =>
      YandexUploadTargets.fromJson(await _run('yandex_upload_targets'));

  @override
  Future<YandexUploadResult> uploadTrack({
    required int localFileId,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
  }) async {
    final payload = await _run(
      'yandex_upload_track',
      uploadPayload: {
        'local_file_id': localFileId,
        'playlist_kind': playlistKind,
        'confirm': confirm,
        'rights_confirmed': rightsConfirmed,
      },
    );
    return YandexUploadResult.fromJson(payload);
  }

  Future<Map<String, dynamic>> _run(
    String command, {
    Map<String, dynamic>? uploadPayload,
  }) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePython(repoRoot);
    final separator = Platform.pathSeparator;
    final srcPath = '$repoRoot${separator}src';
    final currentPythonPath = Platform.environment['PYTHONPATH'];
    final environment = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': currentPythonPath == null || currentPythonPath.isEmpty
          ? srcPath
          : '$srcPath${Platform.isWindows ? ';' : ':'}$currentPythonPath',
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    };
    environment.remove('YANDEX_MUSIC_TOKEN');
    environment.remove(_payloadEnv);
    if (uploadPayload != null) {
      environment[_payloadEnv] = jsonEncode(uploadPayload);
    }

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
                  : 'Yandex upload bridge returned invalid JSON.'),
      );
    }
    return decoded;
  }

  String _resolveRepoRoot() {
    final override = Platform.environment['MUSICARK_REPO_ROOT']?.trim();
    if (override != null &&
        override.isNotEmpty &&
        _looksLikeRoot(Directory(override))) {
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
    final s = Platform.pathSeparator;
    return File('${directory.path}${s}pyproject.toml').existsSync() &&
        File(
          '${directory.path}${s}src${s}musicark${s}upload${s}bridge.py',
        ).existsSync();
  }

  Future<_UploadPythonCommand> _resolvePython(String repoRoot) async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) {
      final command = _UploadPythonCommand(override);
      if (await _works(command)) return command;
    }
    final s = Platform.pathSeparator;
    final venv = Platform.isWindows
        ? '$repoRoot${s}.venv${s}Scripts${s}python.exe'
        : '$repoRoot${s}.venv${s}bin${s}python';
    if (File(venv).existsSync()) {
      final command = _UploadPythonCommand(venv);
      if (await _works(command)) return command;
    }
    final candidates = Platform.isWindows
        ? const [
            _UploadPythonCommand('python'),
            _UploadPythonCommand('py', prefixArgs: ['-3']),
          ]
        : const [
            _UploadPythonCommand('python3'),
            _UploadPythonCommand('python'),
          ];
    for (final command in candidates) {
      if (await _works(command)) return command;
    }
    throw const MusicArkBridgeException(
      'python_not_found',
      'Python was not found.',
    );
  }

  Future<bool> _works(_UploadPythonCommand command) async {
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

class _UploadPythonCommand {
  const _UploadPythonCommand(this.executable, {this.prefixArgs = const []});

  final String executable;
  final List<String> prefixArgs;
}

class FakeYandexUploadBridge implements YandexUploadBridgeClient {
  FakeYandexUploadBridge({
    this.authenticated = true,
    this.playlists = const [
      YandexUploadTarget(
        playlistKind: '1055',
        title: 'Upload test',
        trackCount: 0,
      ),
    ],
    this.nextResult,
  });

  final bool authenticated;
  final List<YandexUploadTarget> playlists;
  final YandexUploadResult? nextResult;
  final List<Map<String, dynamic>> submissions = [];

  @override
  Future<YandexUploadTargets> targets() async => YandexUploadTargets(
    authenticated: authenticated,
    playlists: playlists,
  );

  @override
  Future<YandexUploadResult> uploadTrack({
    required int localFileId,
    required String playlistKind,
    required bool confirm,
    required bool rightsConfirmed,
  }) async {
    submissions.add({
      'local_file_id': localFileId,
      'playlist_kind': playlistKind,
      'confirm': confirm,
      'rights_confirmed': rightsConfirmed,
    });
    return nextResult ??
        YandexUploadResult(
          status: YandexUploadStatus.verified,
          localFileId: localFileId,
          playlistKind: playlistKind,
          trackId: 'ugc-1',
          readBackVerified: true,
          readBackAttempts: 1,
          safeMessage: 'verified',
        );
  }
}
