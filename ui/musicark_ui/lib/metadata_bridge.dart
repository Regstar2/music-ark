import 'dart:convert';
import 'dart:io';

import 'musicark_bridge.dart';

abstract interface class MetadataBridgeClient {
  Future<Map<String, dynamic>> getMetadata(int localFileId);
  Future<Map<String, dynamic>> updateMetadata(int localFileId, Map<String, dynamic> changes);
  Future<Map<String, dynamic>> artworkBatch(List<int> localFileIds);
  Future<Map<String, dynamic>> searchYandex(int localFileId, {String query = ''});
  Future<Map<String, dynamic>> getYandex(String externalId);
  Future<Map<String, dynamic>> compareYandex(int localFileId, String externalId);
  Future<Map<String, dynamic>> applyYandex(
    int localFileId,
    String externalId,
    List<String> selectedFields, {
    required bool bindIdentity,
  });
}

class MetadataBridge implements MetadataBridgeClient {
  const MetadataBridge();

  @override
  Future<Map<String, dynamic>> getMetadata(int localFileId) =>
      _run('local_metadata_get', localFileId: localFileId);

  @override
  Future<Map<String, dynamic>> updateMetadata(int localFileId, Map<String, dynamic> changes) =>
      _run(
        'local_metadata_update',
        localFileId: localFileId,
        payload: {'confirm': true, 'changes': changes},
      );

  @override
  Future<Map<String, dynamic>> artworkBatch(List<int> localFileIds) =>
      _run('local_artwork_batch', localFileIds: localFileIds);

  @override
  Future<Map<String, dynamic>> searchYandex(int localFileId, {String query = ''}) =>
      _run('yandex_metadata_search', localFileId: localFileId, query: query);

  @override
  Future<Map<String, dynamic>> getYandex(String externalId) =>
      _run('yandex_metadata_get', externalId: externalId);

  @override
  Future<Map<String, dynamic>> compareYandex(int localFileId, String externalId) =>
      _run('local_metadata_compare_yandex', localFileId: localFileId, externalId: externalId);

  @override
  Future<Map<String, dynamic>> applyYandex(
    int localFileId,
    String externalId,
    List<String> selectedFields, {
    required bool bindIdentity,
  }) =>
      _run(
        'local_metadata_apply_yandex',
        localFileId: localFileId,
        externalId: externalId,
        bindIdentity: bindIdentity,
        payload: {'confirm': true, 'selectedFields': selectedFields},
      );

  Future<Map<String, dynamic>> _run(
    String command, {
    int? localFileId,
    String? externalId,
    String? query,
    bool bindIdentity = false,
    Map<String, dynamic>? payload,
    List<int>? localFileIds,
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
    // The editor backend reads the Yandex token from the same OS credential store as
    // the rest of MusicArk. Credentials are never copied into this process payload.
    environment.remove('YANDEX_MUSIC_TOKEN');
    if (payload != null) {
      environment['MUSICARK_METADATA_PAYLOAD'] = jsonEncode(payload);
    }
    if (localFileIds != null) {
      environment['MUSICARK_LOCAL_FILE_IDS'] = jsonEncode(localFileIds);
    }
    final args = <String>[
      ...python.prefixArgs,
      '-m',
      'musicark.metadata.bridge',
      '--base-dir',
      repoRoot,
      command,
      if (localFileId != null) ...['--local-file-id', '$localFileId'],
      if (externalId != null && externalId.isNotEmpty) ...['--external-id', externalId],
      if (query != null && query.isNotEmpty) ...['--query', query],
      if (bindIdentity) '--bind-identity',
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
        stderrText.isNotEmpty ? stderrText : (stdoutText.isNotEmpty ? stdoutText : 'Metadata bridge returned invalid JSON.'),
      );
    }
    return decoded;
  }

  String _resolveRepoRoot() {
    final override = Platform.environment['MUSICARK_REPO_ROOT']?.trim();
    if (override != null && override.isNotEmpty && _looksLikeRoot(Directory(override))) {
      return Directory(override).absolute.path;
    }
    final starts = <Directory>{Directory.current.absolute, File(Platform.resolvedExecutable).parent.absolute};
    for (final start in starts) {
      var current = start;
      while (true) {
        if (_looksLikeRoot(current)) return current.path;
        final parent = current.parent;
        if (parent.path == current.path) break;
        current = parent;
      }
    }
    throw const MusicArkBridgeException('repo_root_not_found', 'MusicArk repository root was not found.');
  }

  bool _looksLikeRoot(Directory directory) {
    final s = Platform.pathSeparator;
    return File('${directory.path}${s}pyproject.toml').existsSync() &&
        File('${directory.path}${s}src${s}musicark${s}metadata${s}bridge.py').existsSync();
  }

  Future<_MetadataPythonCommand> _resolvePython(String repoRoot) async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) {
      final command = _MetadataPythonCommand(override);
      if (await _works(command)) return command;
    }
    final s = Platform.pathSeparator;
    final venv = Platform.isWindows
        ? '$repoRoot${s}.venv${s}Scripts${s}python.exe'
        : '$repoRoot${s}.venv${s}bin${s}python';
    if (File(venv).existsSync()) {
      final command = _MetadataPythonCommand(venv);
      if (await _works(command)) return command;
    }
    final candidates = Platform.isWindows
        ? const [_MetadataPythonCommand('python'), _MetadataPythonCommand('py', prefixArgs: ['-3'])]
        : const [_MetadataPythonCommand('python3'), _MetadataPythonCommand('python')];
    for (final command in candidates) {
      if (await _works(command)) return command;
    }
    throw const MusicArkBridgeException('python_not_found', 'Python was not found.');
  }

  Future<bool> _works(_MetadataPythonCommand command) async {
    try {
      final result = await Process.run(command.executable, [...command.prefixArgs, '--version'], runInShell: false);
      return result.exitCode == 0;
    } on ProcessException {
      return false;
    }
  }
}

class _MetadataPythonCommand {
  const _MetadataPythonCommand(this.executable, {this.prefixArgs = const []});
  final String executable;
  final List<String> prefixArgs;
}

class FakeMetadataBridge implements MetadataBridgeClient {
  FakeMetadataBridge({
    Map<int, Map<String, dynamic>>? documents,
    this.searchItems = const [],
  }) : documents = documents ?? {};

  final Map<int, Map<String, dynamic>> documents;
  final List<Map<String, dynamic>> searchItems;
  final List<Map<String, dynamic>> updates = [];
  final List<Map<String, dynamic>> applies = [];

  @override
  Future<Map<String, dynamic>> artworkBatch(List<int> localFileIds) async => {
        'items': {
          for (final id in localFileIds)
            '$id': documents[id]?['artwork'] ?? {'present': false, 'cachePath': null},
        },
      };

  @override
  Future<Map<String, dynamic>> getMetadata(int localFileId) async => {
        'metadata': documents[localFileId] ??
            {
              'localFileId': localFileId,
              'path': r'C:\Music\Track.mp3',
              'format': 'mp3',
              'writable': true,
              'fields': <String, dynamic>{},
              'allTags': <Map<String, dynamic>>[],
              'artwork': {'present': false, 'cachePath': null},
              'identity': {'status': 'not_set'},
              'technical': <String, dynamic>{},
            },
      };

  @override
  Future<Map<String, dynamic>> updateMetadata(int localFileId, Map<String, dynamic> changes) async {
    updates.add({'localFileId': localFileId, 'changes': changes});
    final document = Map<String, dynamic>.from((await getMetadata(localFileId))['metadata'] as Map);
    final fields = Map<String, dynamic>.from(document['fields'] as Map? ?? const {});
    final fieldChanges = Map<String, dynamic>.from(changes)
      ..remove('artworkImagePath')
      ..remove('removeArtwork')
      ..remove('textFrames')
      ..remove('customTextTags');
    fields.addAll(fieldChanges);
    document['fields'] = fields;
    documents[localFileId] = document;
    return {'metadata': document, 'matching': {'recalculated': 1}};
  }

  @override
  Future<Map<String, dynamic>> searchYandex(int localFileId, {String query = ''}) async => {
        'query': query.isEmpty ? 'Track' : query,
        'count': searchItems.length,
        'items': searchItems,
      };

  @override
  Future<Map<String, dynamic>> getYandex(String externalId) async => {
        'track': searchItems.firstWhere((item) => '${(item['identity'] as Map?)?['externalId']}' == externalId),
      };

  @override
  Future<Map<String, dynamic>> compareYandex(int localFileId, String externalId) async {
    final local = (await getMetadata(localFileId))['metadata'];
    final yandex = (await getYandex(externalId))['track'];
    final yf = Map<String, dynamic>.from((yandex as Map)['fields'] as Map? ?? const {});
    final lf = Map<String, dynamic>.from((local as Map)['fields'] as Map? ?? const {});
    final rows = <Map<String, dynamic>>[];
    for (final entry in yf.entries) {
      rows.add({'field': entry.key, 'local': lf[entry.key], 'yandex': entry.value, 'available': entry.value != null, 'selected': entry.value != null});
    }
    rows.add({'field': 'artwork', 'local': false, 'yandex': true, 'available': true, 'selected': true});
    return {'local': local, 'yandex': yandex, 'rows': rows};
  }

  @override
  Future<Map<String, dynamic>> applyYandex(
    int localFileId,
    String externalId,
    List<String> selectedFields, {
    required bool bindIdentity,
  }) async {
    applies.add({
      'localFileId': localFileId,
      'externalId': externalId,
      'selectedFields': List<String>.from(selectedFields),
      'bindIdentity': bindIdentity,
    });
    return {
      'identity': bindIdentity
          ? {'status': 'matched', 'method': 'exact_id', 'confidence': 1.0, 'reason': 'user_confirmed'}
          : null,
      'matching': {'recalculated': 1},
    };
  }
}
