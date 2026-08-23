import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';

abstract interface class ExternalMetadataBridgeClient {
  Future<Map<String, dynamic>> identify(
    int localFileId, {
    bool continueSearch = false,
  });
  Future<Map<String, dynamic>> search(
    int localFileId, {
    required String title,
    String artist = '',
    String album = '',
    bool continueSearch = false,
  });
  Future<Map<String, dynamic>> compare(int localFileId, String candidateId);
  Future<Map<String, dynamic>> apply(
    int localFileId,
    String candidateId,
    List<String> selectedFields,
  );
  Future<Map<String, dynamic>> getNetworkSettings();
  Future<Map<String, dynamic>> updateNetworkSettings(
    Map<String, dynamic> settings,
  );
  Future<Map<String, dynamic>> testNetwork();
  Future<Map<String, dynamic>> getExternalCredentialStatus();
  Future<Map<String, dynamic>> updateExternalCredentials(
    Map<String, dynamic> credentials,
  );
}

class ExternalMetadataBridge implements ExternalMetadataBridgeClient {
  const ExternalMetadataBridge();

  @override
  Future<Map<String, dynamic>> identify(
    int localFileId, {
    bool continueSearch = false,
  }) =>
      _run(
        'external_metadata_identify',
        localFileId: localFileId,
        continueSearch: continueSearch,
      );

  @override
  Future<Map<String, dynamic>> search(
    int localFileId, {
    required String title,
    String artist = '',
    String album = '',
    bool continueSearch = false,
  }) =>
      _run(
        'external_metadata_search',
        localFileId: localFileId,
        title: title,
        artist: artist,
        album: album,
        continueSearch: continueSearch,
      );

  @override
  Future<Map<String, dynamic>> compare(int localFileId, String candidateId) =>
      _run(
        'external_metadata_compare',
        localFileId: localFileId,
        candidateId: candidateId,
      );

  @override
  Future<Map<String, dynamic>> apply(
    int localFileId,
    String candidateId,
    List<String> selectedFields,
  ) =>
      _run(
        'external_metadata_apply',
        localFileId: localFileId,
        candidateId: candidateId,
        payload: {
          'confirm': true,
          'selectedFields': selectedFields,
        },
      );

  @override
  Future<Map<String, dynamic>> getNetworkSettings() =>
      _run('network_settings_get');

  @override
  Future<Map<String, dynamic>> updateNetworkSettings(
    Map<String, dynamic> settings,
  ) =>
      _run('network_settings_update', payload: settings);

  @override
  Future<Map<String, dynamic>> testNetwork() => _run('network_test');

  @override
  Future<Map<String, dynamic>> getExternalCredentialStatus() =>
      _run('external_credentials_get');

  @override
  Future<Map<String, dynamic>> updateExternalCredentials(
    Map<String, dynamic> credentials,
  ) =>
      _run('external_credentials_update', payload: credentials);

  Future<Map<String, dynamic>> _run(
    String command, {
    int? localFileId,
    String candidateId = '',
    String title = '',
    String artist = '',
    String album = '',
    bool continueSearch = false,
    Map<String, dynamic>? payload,
  }) async {
    final root = _resolveRepoRoot();
    final python = await _resolvePython(root);
    final separator = Platform.pathSeparator;
    final src = '$root${separator}src';
    final current = Platform.environment['PYTHONPATH'];
    final environment = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': current == null || current.isEmpty
          ? src
          : '$src${Platform.isWindows ? ';' : ':'}$current',
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    };
    environment.remove('YANDEX_MUSIC_TOKEN');
    if (payload != null) {
      environment['MUSICARK_EXTERNAL_PAYLOAD'] = jsonEncode(payload);
    }
    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.external_metadata.bridge',
      '--base-dir',
      root,
      command,
      if (localFileId != null) ...['--local-file-id', '$localFileId'],
      if (candidateId.isNotEmpty) ...['--candidate-id', candidateId],
      if (title.isNotEmpty) ...['--title', title],
      if (artist.isNotEmpty) ...['--artist', artist],
      if (album.isNotEmpty) ...['--album', album],
      if (continueSearch) '--continue-search',
    ];
    final result = await Process.run(
      python.executable,
      args,
      workingDirectory: root,
      runInShell: false,
      environment: environment,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    final stdout = '${result.stdout ?? ''}'.trim();
    final stderr = '${result.stderr ?? ''}'.trim();
    Map<String, dynamic>? decoded;
    try {
      final value = stdout.isEmpty ? null : jsonDecode(stdout);
      if (value is Map) decoded = Map<String, dynamic>.from(value);
    } on FormatException {
      decoded = null;
    }
    if (decoded?['error'] is Map) {
      final error = Map<String, dynamic>.from(decoded!['error'] as Map);
      throw MusicArkBridgeException(
        '${error['code'] ?? 'external_metadata_error'}',
        '${error['message'] ?? stderr}',
      );
    }
    if (result.exitCode != 0 || decoded == null) {
      throw MusicArkBridgeException(
        'external_metadata_error',
        stderr.isNotEmpty
            ? stderr
            : (stdout.isNotEmpty
                ? stdout
                : 'External metadata bridge returned invalid JSON.'),
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
    final separator = Platform.pathSeparator;
    return File(
          '${directory.path}${separator}pyproject.toml',
        ).existsSync() &&
        File(
          '${directory.path}${separator}src${separator}musicark${separator}external_metadata${separator}bridge.py',
        ).existsSync();
  }

  Future<_PythonCommand> _resolvePython(String root) async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) {
      final command = _PythonCommand(override);
      if (await _works(command)) return command;
    }
    final separator = Platform.pathSeparator;
    final venv = Platform.isWindows
        ? '$root${separator}.venv${separator}Scripts${separator}python.exe'
        : '$root${separator}.venv${separator}bin${separator}python';
    if (File(venv).existsSync()) {
      final command = _PythonCommand(venv);
      if (await _works(command)) return command;
    }
    final candidates = Platform.isWindows
        ? const [
            _PythonCommand('python'),
            _PythonCommand('py', prefixArgs: ['-3']),
          ]
        : const [_PythonCommand('python3'), _PythonCommand('python')];
    for (final command in candidates) {
      if (await _works(command)) return command;
    }
    throw const MusicArkBridgeException(
      'python_not_found',
      'Python was not found.',
    );
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

class FakeExternalMetadataBridge implements ExternalMetadataBridgeClient {
  FakeExternalMetadataBridge({
    this.networkMode = 'system',
    this.candidates = const [],
  });

  String networkMode;
  final List<Map<String, dynamic>> candidates;
  final Map<String, dynamic> credentialStatus = {
    'acoustid': {
      'configured': false,
      'origin': 'missing',
      'advanced': true,
    },
    'discogs': {
      'configured': false,
      'origin': 'missing',
      'advanced': true,
    },
    'theaudiodb': {
      'configured': true,
      'origin': 'builtin_free',
      'advanced': false,
    },
    'lastfm': {
      'configured': false,
      'origin': 'missing',
      'advanced': true,
    },
  };

  @override
  Future<Map<String, dynamic>> identify(
    int localFileId, {
    bool continueSearch = false,
  }) async =>
      {
        'items': candidates,
        'sources': const [],
        'earlyStop': !continueSearch,
      };

  @override
  Future<Map<String, dynamic>> search(
    int localFileId, {
    required String title,
    String artist = '',
    String album = '',
    bool continueSearch = false,
  }) async =>
      {'items': candidates, 'sources': const []};

  @override
  Future<Map<String, dynamic>> compare(
    int localFileId,
    String candidateId,
  ) async =>
      {'rows': const []};

  @override
  Future<Map<String, dynamic>> apply(
    int localFileId,
    String candidateId,
    List<String> selectedFields,
  ) async =>
      {
        'external': {'appliedFields': selectedFields},
      };

  @override
  Future<Map<String, dynamic>> getNetworkSettings() async =>
      {
        'settings': {
          'mode': networkMode,
          'proxyScheme': 'socks5',
          'proxyHost': '127.0.0.1',
          'proxyPort': 1080,
          'proxyUsername': '',
          'proxyPasswordConfigured': false,
        },
      };

  @override
  Future<Map<String, dynamic>> updateNetworkSettings(
    Map<String, dynamic> settings,
  ) async {
    networkMode = '${settings['networkMode'] ?? networkMode}';
    return getNetworkSettings();
  }

  @override
  Future<Map<String, dynamic>> testNetwork() async =>
      {
        'items': const [],
        'settings': {
          'mode': networkMode,
        },
      };

  @override
  Future<Map<String, dynamic>> getExternalCredentialStatus() async =>
      {'credentials': credentialStatus};

  @override
  Future<Map<String, dynamic>> updateExternalCredentials(
    Map<String, dynamic> credentials,
  ) async {
    for (final entry in credentials.entries) {
      final provider = switch (entry.key) {
        'acoustid_key' => 'acoustid',
        'discogs_token' => 'discogs',
        'theaudiodb_key' => 'theaudiodb',
        'lastfm_key' => 'lastfm',
        _ => '',
      };
      if (provider.isNotEmpty) {
        credentialStatus[provider] = {
          'configured': '${entry.value}'.trim().isNotEmpty,
          'origin': '${entry.value}'.trim().isNotEmpty
              ? 'keyring'
              : 'missing',
          'advanced': provider != 'theaudiodb',
        };
      }
    }
    return {'credentials': credentialStatus};
  }
}
