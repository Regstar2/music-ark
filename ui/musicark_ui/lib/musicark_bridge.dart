import 'dart:convert';
import 'dart:io';

import 'app_strings.dart';

abstract interface class MusicArkBridgeClient {
  Future<Map<String, dynamic>> bootstrap();
  Future<Map<String, dynamic>> login(String token);
  Future<Map<String, dynamic>> likedRefresh();
  Future<Map<String, dynamic>> playlists();
  Future<Map<String, dynamic>> playlist(String externalId);
  Future<Map<String, dynamic>> playlistRefresh(String externalId);
  Future<Map<String, dynamic>> libraryRefresh();
  Future<Map<String, dynamic>> logout();

  Future<Map<String, dynamic>> localRoots();
  Future<Map<String, dynamic>> localRootAdd(String path);
  Future<Map<String, dynamic>> localRootRemove(int rootId);
  Future<Map<String, dynamic>> localScan({int? rootId});
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
  });
  Future<Map<String, dynamic>> localTrack(int trackId);
  Future<Map<String, dynamic>> localStats();
}

class MusicArkBridge implements MusicArkBridgeClient {
  @override
  Future<Map<String, dynamic>> bootstrap() => _runBridge('bootstrap');
  @override
  Future<Map<String, dynamic>> login(String token) => _runBridge('login', token: token);
  @override
  Future<Map<String, dynamic>> likedRefresh() => _runBridge('liked_refresh');
  @override
  Future<Map<String, dynamic>> playlists() => _runBridge('playlists');
  @override
  Future<Map<String, dynamic>> playlist(String externalId) => _runBridge('playlist', playlistId: externalId);
  @override
  Future<Map<String, dynamic>> playlistRefresh(String externalId) => _runBridge('playlist_refresh', playlistId: externalId);
  @override
  Future<Map<String, dynamic>> libraryRefresh() => _runBridge('library_refresh');
  @override
  Future<Map<String, dynamic>> logout() => _runBridge('logout');

  @override
  Future<Map<String, dynamic>> localRoots() => _runBridge('local_roots');
  @override
  Future<Map<String, dynamic>> localRootAdd(String path) => _runBridge('local_root_add', localRootPath: path);
  @override
  Future<Map<String, dynamic>> localRootRemove(int rootId) => _runBridge('local_root_remove', rootId: rootId);
  @override
  Future<Map<String, dynamic>> localScan({int? rootId}) => _runBridge('local_scan', rootId: rootId);
  @override
  Future<Map<String, dynamic>> localTracks({int limit = 1000, int offset = 0, String search = '', String sort = 'artist', int? rootId}) =>
      _runBridge('local_tracks', rootId: rootId, limit: limit, offset: offset, search: search, sort: sort);
  @override
  Future<Map<String, dynamic>> localTrack(int trackId) => _runBridge('local_track', trackId: trackId);
  @override
  Future<Map<String, dynamic>> localStats() => _runBridge('local_stats');

  Future<Map<String, dynamic>> _runBridge(
    String command, {
    String? token,
    String? playlistId,
    String? localRootPath,
    int? rootId,
    int? trackId,
    int? limit,
    int? offset,
    String? search,
    String? sort,
  }) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePythonCommand();
    final srcPath = '$repoRoot${Platform.pathSeparator}src';
    final existingPythonPath = Platform.environment['PYTHONPATH'];
    final mergedPythonPath = existingPythonPath == null || existingPythonPath.isEmpty
        ? srcPath
        : '$srcPath${Platform.isWindows ? ';' : ':'}$existingPythonPath';
    final bridgeEnv = <String, String>{
      ...Platform.environment,
      'PYTHONPATH': mergedPythonPath,
      'PYTHONIOENCODING': 'utf-8',
      'PYTHONUTF8': '1',
    };
    bridgeEnv.remove('YANDEX_MUSIC_TOKEN');
    bridgeEnv.remove('MUSICARK_LOCAL_ROOT');
    if (token != null && token.isNotEmpty) bridgeEnv['YANDEX_MUSIC_TOKEN'] = token;
    if (localRootPath != null && localRootPath.isNotEmpty) bridgeEnv['MUSICARK_LOCAL_ROOT'] = localRootPath;

    final args = <String>[
      ...python.prefixArgs,
      '-m', 'musicark.mvp_bridge', '--base-dir', repoRoot, command,
      if (playlistId != null) ...['--playlist-id', playlistId],
      if (rootId != null) ...['--root-id', '$rootId'],
      if (trackId != null) ...['--track-id', '$trackId'],
      if (limit != null) ...['--limit', '$limit'],
      if (offset != null) ...['--offset', '$offset'],
      if (search != null && search.isNotEmpty) ...['--search', search],
      if (sort != null && sort.isNotEmpty) ...['--sort', sort],
    ];
    final result = await Process.run(
      python.executable,
      args,
      runInShell: false,
      workingDirectory: repoRoot,
      environment: bridgeEnv,
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
      throw MusicArkBridgeException((error['code'] ?? 'unexpected_error').toString(), (error['message'] ?? stderrText).toString());
    }
    if (result.exitCode != 0) {
      throw MusicArkBridgeException('unexpected_error', stderrText.isNotEmpty ? stderrText : stdoutText);
    }
    if (payload == null) {
      throw MusicArkBridgeException('unexpected_error', stderrText.isNotEmpty ? stderrText : 'Bridge returned invalid JSON.');
    }
    return payload;
  }

  String _resolveRepoRoot() {
    final override = Platform.environment['MUSICARK_REPO_ROOT']?.trim();
    if (override != null && override.isNotEmpty) {
      final directory = Directory(override);
      if (_looksLikeRepoRoot(directory)) return directory.absolute.path;
    }
    final candidates = <Directory>{Directory.current.absolute, File(Platform.resolvedExecutable).parent.absolute};
    for (final start in candidates) {
      var current = start;
      while (true) {
        if (_looksLikeRepoRoot(current)) return current.path;
        final parent = current.parent;
        if (parent.path == current.path) break;
        current = parent;
      }
    }
    throw const MusicArkBridgeException('repo_root_not_found', AppStrings.repoRootNotFound);
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
        final result = await Process.run(candidate.executable, [...candidate.prefixArgs, '--version'], runInShell: false);
        if (result.exitCode == 0) return candidate;
      } on ProcessException {
        // Try the next launcher.
      }
    }
    throw const MusicArkBridgeException('python_not_found', AppStrings.pythonNotFound);
  }
}

class _PythonCommand {
  const _PythonCommand(this.executable, {this.prefixArgs = const []});
  final String executable;
  final List<String> prefixArgs;
}

class MusicArkBridgeException implements Exception {
  const MusicArkBridgeException(this.code, this.message);
  final String code;
  final String message;
  @override
  String toString() => '$code: $message';
}

class FakeMusicArkBridge implements MusicArkBridgeClient {
  FakeMusicArkBridge({this.startSignedIn = false, this.failLibraryRefresh = false, this.failPlaylistRefresh = false});
  final bool startSignedIn;
  final bool failLibraryRefresh;
  final bool failPlaylistRefresh;
  int libraryRefreshCalls = 0;
  int likedRefreshCalls = 0;
  int playlistRefreshCalls = 0;
  int localScanCalls = 0;
  final List<Map<String, dynamic>> _localRoots = [];

  static const _account = {'provider': 'yandex_music', 'providerUserId': 'test-user', 'displayName': 'Tester'};
  static const _likedTracks = [
    {'provider_id': 'yandex_music', 'external_id': '101', 'title': 'Courtesy Call', 'artists': ['Thousand Foot Krutch'], 'album_title': 'The End Is Where We Begin', 'duration_seconds': 238, 'availability': 'available'},
    {'provider_id': 'yandex_music', 'external_id': '102', 'title': 'Animal I Have Become', 'artists': ['Three Days Grace'], 'album_title': 'One-X', 'duration_seconds': 231, 'availability': 'available'},
  ];
  static const _playlistItems = [
    {'externalId': '501', 'title': 'Rock', 'ownerName': 'Tester', 'trackCount': 2, 'lastUpdated': '2026-08-12T06:15:00+00:00', 'contentLastUpdated': '2026-08-12T06:00:00+00:00', 'sourcePosition': 0},
    {'externalId': '502', 'title': 'Daily Mix', 'ownerName': 'Tester', 'trackCount': 1, 'lastUpdated': '2026-08-12T06:15:00+00:00', 'contentLastUpdated': null, 'sourcePosition': 1},
  ];
  static const _playlistTracks = {
    '501': [
      {'provider_id': 'yandex_music', 'external_id': '201', 'title': 'Numb', 'artists': ['Linkin Park'], 'album_title': 'Meteora', 'duration_seconds': 185, 'availability': 'available'},
      {'provider_id': 'yandex_music', 'external_id': '202', 'title': 'Bring Me to Life', 'artists': ['Evanescence'], 'album_title': 'Fallen', 'duration_seconds': 235, 'availability': 'available'},
    ],
    '502': [
      {'provider_id': 'yandex_music', 'external_id': '203', 'title': 'Monster', 'artists': ['Skillet'], 'album_title': 'Awake', 'duration_seconds': 178, 'availability': 'available'},
    ],
  };
  static const _localTracks = [
    {'id': 1, 'rootId': 1, 'path': r'C:\Music\Artist\Song.flac', 'fileName': 'Song.flac', 'title': 'Song', 'artists': ['Artist'], 'album': 'Album', 'durationSeconds': 245.0, 'codec': 'flac', 'bitrate': 900000, 'sampleRate': 44100},
    {'id': 2, 'rootId': 1, 'path': r'C:\Music\Other.mp3', 'fileName': 'Other.mp3', 'title': 'Other', 'artists': ['Another Artist'], 'album': 'Singles', 'durationSeconds': 180.0, 'codec': 'mp3', 'bitrate': 320000, 'sampleRate': 44100},
  ];

  Map<String, dynamic> _libraryState({required bool signedIn, required String source}) {
    final liked = {
      'source': signedIn ? source : 'none',
      'count': signedIn ? _likedTracks.length : 0,
      'lastUpdated': signedIn ? '2026-08-12T06:15:00+00:00' : null,
      'tracks': signedIn ? _likedTracks : <Map<String, dynamic>>[],
      'diff': {'added': 0, 'removed': 0, 'unchanged': signedIn ? _likedTracks.length : 0},
    };
    return {
      'session': {'hasStoredToken': signedIn, 'account': signedIn ? _account : <String, dynamic>{}},
      'liked': liked,
      'library': liked,
      'playlists': {
        'source': signedIn ? source : 'none',
        'count': signedIn ? _playlistItems.length : 0,
        'lastUpdated': signedIn ? '2026-08-12T06:15:00+00:00' : null,
        'items': signedIn ? _playlistItems : <Map<String, dynamic>>[],
        'diff': {'added': 0, 'removed': 0, 'unchanged': signedIn ? _playlistItems.length : 0},
      },
    };
  }

  Map<String, dynamic> _playlistState(String externalId, String source) {
    final metadata = _playlistItems.firstWhere((item) => item['externalId'] == externalId, orElse: () => {'externalId': externalId, 'title': 'Unknown', 'trackCount': 0});
    final tracks = _playlistTracks[externalId] ?? const <Map<String, dynamic>>[];
    return {
      'session': {'hasStoredToken': true, 'account': _account},
      'playlist': metadata,
      'collection': {'source': source, 'count': tracks.length, 'lastUpdated': '2026-08-12T06:00:00+00:00', 'tracks': tracks, 'diff': {'added': 0, 'removed': 0, 'unchanged': tracks.length}},
    };
  }

  @override
  Future<Map<String, dynamic>> bootstrap() async => _libraryState(signedIn: startSignedIn, source: 'cache');
  @override
  Future<Map<String, dynamic>> login(String token) async => _libraryState(signedIn: true, source: 'network');
  @override
  Future<Map<String, dynamic>> likedRefresh() async { likedRefreshCalls++; return _libraryState(signedIn: true, source: 'network'); }
  @override
  Future<Map<String, dynamic>> playlists() async => _libraryState(signedIn: true, source: 'cache');
  @override
  Future<Map<String, dynamic>> playlist(String externalId) async => _playlistState(externalId, 'cache');
  @override
  Future<Map<String, dynamic>> playlistRefresh(String externalId) async {
    playlistRefreshCalls++;
    if (failPlaylistRefresh) throw const MusicArkBridgeException('yandex_request_failed', 'offline');
    return _playlistState(externalId, 'network');
  }
  @override
  Future<Map<String, dynamic>> libraryRefresh() async {
    libraryRefreshCalls++;
    if (failLibraryRefresh) throw const MusicArkBridgeException('yandex_request_failed', 'offline');
    return _libraryState(signedIn: true, source: 'network');
  }
  @override
  Future<Map<String, dynamic>> logout() async => _libraryState(signedIn: false, source: 'none');

  @override
  Future<Map<String, dynamic>> localRoots() async => {'count': _localRoots.length, 'items': List<Map<String, dynamic>>.from(_localRoots)};
  @override
  Future<Map<String, dynamic>> localRootAdd(String path) async {
    final root = {'id': _localRoots.length + 1, 'path': path, 'normalizedPath': path.toLowerCase(), 'enabled': true, 'createdAt': '2026-08-14T00:00:00Z', 'lastScannedAt': null};
    _localRoots.add(root);
    return {'root': root, 'roots': await localRoots()};
  }
  @override
  Future<Map<String, dynamic>> localRootRemove(int rootId) async {
    _localRoots.removeWhere((item) => item['id'] == rootId);
    return {'removed': true, 'roots': await localRoots()};
  }
  @override
  Future<Map<String, dynamic>> localScan({int? rootId}) async {
    localScanCalls++;
    return {'added': 2, 'updated': 0, 'removed': 0, 'unchanged': 0, 'errors': 0, 'scanned': 2, 'errorItems': <Map<String, dynamic>>[]};
  }
  @override
  Future<Map<String, dynamic>> localTracks({int limit = 1000, int offset = 0, String search = '', String sort = 'artist', int? rootId}) async {
    var items = _localRoots.isEmpty ? <Map<String, dynamic>>[] : List<Map<String, dynamic>>.from(_localTracks);
    final q = search.toLowerCase();
    if (q.isNotEmpty) {
      items = items.where((item) => '${item['title']} ${item['artists']} ${item['album']} ${item['fileName']}'.toLowerCase().contains(q)).toList();
    }
    return {'count': items.length, 'limit': limit, 'offset': offset, 'items': items};
  }
  @override
  Future<Map<String, dynamic>> localTrack(int trackId) async => {'track': _localTracks.firstWhere((item) => item['id'] == trackId)};
  @override
  Future<Map<String, dynamic>> localStats() async => {'total_files': _localRoots.isEmpty ? 0 : _localTracks.length, 'enabled_roots': _localRoots.length, 'by_codec': {'flac': 1, 'mp3': 1}};
}
