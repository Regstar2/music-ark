import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import 'app_strings.dart';

void main() {
  runApp(const MusicArkDesktopApp());
}

class MusicArkDesktopApp extends StatelessWidget {
  const MusicArkDesktopApp({super.key, this.bridge});

  final MusicArkBridgeClient? bridge;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppStrings.appTitle,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: MusicArkHomePage(bridge: bridge ?? MusicArkBridge()),
    );
  }
}

enum LibrarySort { original, title, artist }

class MusicArkHomePage extends StatefulWidget {
  const MusicArkHomePage({super.key, required this.bridge});

  final MusicArkBridgeClient bridge;

  @override
  State<MusicArkHomePage> createState() => _MusicArkHomePageState();
}

class _MusicArkHomePageState extends State<MusicArkHomePage> {
  final TextEditingController _tokenController = TextEditingController();
  final TextEditingController _searchController = TextEditingController();

  bool _initializing = true;
  bool _busy = false;
  bool _tokenVisible = false;
  bool _hasStoredToken = false;
  String? _errorMessage;
  String? _errorDetails;
  Map<String, dynamic> _account = const {};
  List<Map<String, dynamic>> _tracks = const [];
  String _source = 'none';
  String? _lastUpdated;
  LibrarySort _sortMode = LibrarySort.original;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  @override
  void dispose() {
    _tokenController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _initialize() async {
    try {
      final payload = await widget.bridge.bootstrap();
      if (!mounted) return;
      _applyPayload(payload);
      setState(() => _initializing = false);
      if (_hasStoredToken) {
        await _refreshLikes(showDiff: false);
      }
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      setState(() {
        _initializing = false;
        _errorMessage = _messageForBridgeError(error.code);
        _errorDetails = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _initializing = false;
        _errorMessage = AppStrings.unexpectedError;
        _errorDetails = error.toString();
      });
    }
  }

  Future<void> _signIn() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      setState(() {
        _errorMessage = AppStrings.tokenRequired;
        _errorDetails = null;
      });
      return;
    }

    setState(() {
      _busy = true;
      _errorMessage = null;
      _errorDetails = null;
    });

    try {
      final payload = await widget.bridge.login(token);
      if (!mounted) return;
      _applyPayload(payload);
      _tokenController.clear();
      _showSyncDiff(payload);
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = _messageForBridgeError(error.code);
        _errorDetails = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = AppStrings.unexpectedError;
        _errorDetails = error.toString();
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _refreshLikes({bool showDiff = true}) async {
    setState(() {
      _busy = true;
      _errorMessage = null;
      _errorDetails = null;
    });

    try {
      final payload = await widget.bridge.refresh();
      if (!mounted) return;
      _applyPayload(payload);
      if (showDiff) _showSyncDiff(payload);
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = _messageForBridgeError(error.code);
        _errorDetails = error.message;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = AppStrings.unexpectedError;
        _errorDetails = error.toString();
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _logout() async {
    setState(() {
      _busy = true;
      _errorMessage = null;
      _errorDetails = null;
    });
    try {
      final payload = await widget.bridge.logout();
      if (!mounted) return;
      _applyPayload(payload);
      _searchController.clear();
      _tokenController.clear();
      setState(() => _sortMode = LibrarySort.original);
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = _messageForBridgeError(error.code);
        _errorDetails = error.message;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _applyPayload(Map<String, dynamic> payload) {
    final session = _asMap(payload['session']);
    final library = _asMap(payload['library']);
    final account = _asMap(session['account']);
    final rawTracks = library['tracks'];
    final tracks = rawTracks is List
        ? rawTracks
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList(growable: false)
        : <Map<String, dynamic>>[];

    setState(() {
      _hasStoredToken = session['hasStoredToken'] == true;
      _account = account;
      _tracks = tracks;
      _source = (library['source'] ?? 'none').toString();
      _lastUpdated = library['lastUpdated']?.toString();
      _errorMessage = null;
      _errorDetails = null;
    });
  }

  Map<String, dynamic> _asMap(dynamic value) {
    return value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
  }

  void _showSyncDiff(Map<String, dynamic> payload) {
    if (!mounted) return;
    final library = _asMap(payload['library']);
    final diff = _asMap(library['diff']);
    final added = int.tryParse('${diff['added'] ?? 0}') ?? 0;
    final removed = int.tryParse('${diff['removed'] ?? 0}') ?? 0;
    if (added == 0 && removed == 0) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppStrings.syncDiff(added, removed))),
    );
  }

  String _messageForBridgeError(String code) {
    switch (code) {
      case 'token_missing':
        return AppStrings.tokenMissing;
      case 'authentication_failed':
        return AppStrings.authenticationFailed;
      case 'yandex_request_failed':
        return AppStrings.yandexRequestFailed;
      case 'credential_store_failed':
        return AppStrings.credentialStoreFailed;
      case 'cache_failed':
        return AppStrings.cacheFailed;
      case 'python_not_found':
        return AppStrings.pythonNotFound;
      case 'repo_root_not_found':
        return AppStrings.repoRootNotFound;
      default:
        return AppStrings.unexpectedError;
    }
  }

  List<Map<String, dynamic>> get _visibleTracks {
    final query = _searchController.text.trim().toLowerCase();
    final result = _tracks.where((track) {
      if (query.isEmpty) return true;
      final haystack = [
        (track['title'] ?? '').toString(),
        _artistsText(track),
        (track['album_title'] ?? '').toString(),
      ].join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList(growable: false);

    final sorted = List<Map<String, dynamic>>.from(result);
    switch (_sortMode) {
      case LibrarySort.original:
        break;
      case LibrarySort.title:
        sorted.sort((a, b) => _title(a).toLowerCase().compareTo(_title(b).toLowerCase()));
        break;
      case LibrarySort.artist:
        sorted.sort((a, b) => _artistsText(a).toLowerCase().compareTo(_artistsText(b).toLowerCase()));
        break;
    }
    return sorted;
  }

  String _title(Map<String, dynamic> track) =>
      (track['title'] ?? AppStrings.unknownTitle).toString().trim();

  String _artistsText(Map<String, dynamic> track) {
    final raw = track['artists'];
    if (raw is List) {
      final text = raw.map((value) => value.toString()).where((value) => value.isNotEmpty).join(', ');
      if (text.isNotEmpty) return text;
    }
    final text = raw?.toString().trim() ?? '';
    return text.isEmpty ? AppStrings.unknownArtist : text;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('${AppStrings.appTitle} 0.2')),
      body: _initializing
          ? const Center(child: CircularProgressIndicator())
          : _hasStoredToken
              ? _buildLibrary()
              : _buildLogin(),
    );
  }

  Widget _buildLogin() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(AppStrings.loginTitle, style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 12),
                  const Text(AppStrings.loginDescription),
                  const SizedBox(height: 20),
                  TextField(
                    controller: _tokenController,
                    obscureText: !_tokenVisible,
                    enabled: !_busy,
                    onSubmitted: (_) {
                      if (!_busy) _signIn();
                    },
                    decoration: InputDecoration(
                      labelText: AppStrings.tokenLabel,
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        onPressed: _busy
                            ? null
                            : () => setState(() => _tokenVisible = !_tokenVisible),
                        icon: Icon(_tokenVisible ? Icons.visibility_off : Icons.visibility),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _busy ? null : _signIn,
                    child: Text(_busy ? AppStrings.signingIn : AppStrings.signIn),
                  ),
                  if (_errorMessage != null) ...[
                    const SizedBox(height: 16),
                    _ErrorPanel(message: _errorMessage!, details: _errorDetails),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLibrary() {
    final displayName = (_account['displayName'] ?? _account['providerUserId'] ?? '').toString();
    final visible = _visibleTracks;
    final sourceLabel = _source == 'network' ? AppStrings.networkSource : AppStrings.cacheSource;
    final lastUpdated = _lastUpdated ?? AppStrings.neverUpdated;

    return Column(
      children: [
        Material(
          elevation: 1,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(AppStrings.likedTracks, style: Theme.of(context).textTheme.titleLarge),
                          if (displayName.isNotEmpty) Text(displayName),
                          Text(AppStrings.lastUpdated(lastUpdated), style: Theme.of(context).textTheme.bodySmall),
                        ],
                      ),
                    ),
                    Chip(label: Text(sourceLabel)),
                    const SizedBox(width: 12),
                    Text(
                      visible.length == _tracks.length
                          ? AppStrings.trackCount(_tracks.length)
                          : AppStrings.filteredCount(visible.length, _tracks.length),
                    ),
                    const SizedBox(width: 12),
                    IconButton(
                      tooltip: AppStrings.refresh,
                      onPressed: _busy ? null : _refreshLikes,
                      icon: const Icon(Icons.refresh),
                    ),
                    TextButton(
                      onPressed: _busy ? null : _logout,
                      child: const Text(AppStrings.logout),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _searchController,
                        onChanged: (_) => setState(() {}),
                        decoration: const InputDecoration(
                          labelText: AppStrings.search,
                          prefixIcon: Icon(Icons.search),
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    SizedBox(
                      width: 220,
                      child: DropdownButtonFormField<LibrarySort>(
                        value: _sortMode,
                        decoration: const InputDecoration(
                          labelText: AppStrings.sort,
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: LibrarySort.original, child: Text(AppStrings.sortOriginal)),
                          DropdownMenuItem(value: LibrarySort.title, child: Text(AppStrings.sortTitle)),
                          DropdownMenuItem(value: LibrarySort.artist, child: Text(AppStrings.sortArtist)),
                        ],
                        onChanged: _busy
                            ? null
                            : (value) {
                                if (value != null) setState(() => _sortMode = value);
                              },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        if (_busy) const LinearProgressIndicator(),
        if (_errorMessage != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            child: _ErrorPanel(message: _errorMessage!, details: _errorDetails),
          ),
        Expanded(
          child: visible.isEmpty
              ? Center(
                  child: Text(
                    _tracks.isEmpty ? AppStrings.emptyLikes : AppStrings.noSearchResults,
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: visible.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) => _TrackTile(track: visible[index]),
                ),
        ),
      ],
    );
  }
}

class _TrackTile extends StatelessWidget {
  const _TrackTile({required this.track});

  final Map<String, dynamic> track;

  @override
  Widget build(BuildContext context) {
    final title = (track['title'] ?? '').toString().trim();
    final rawArtists = track['artists'];
    final artists = rawArtists is List
        ? rawArtists.map((value) => value.toString()).join(', ')
        : rawArtists?.toString() ?? '';
    final album = (track['album_title'] ?? '').toString().trim();
    final subtitle = [
      artists.isEmpty ? AppStrings.unknownArtist : artists,
      if (album.isNotEmpty) album,
    ].join(' · ');

    return ListTile(
      leading: const Icon(Icons.music_note),
      title: Text(title.isEmpty ? AppStrings.unknownTitle : title),
      subtitle: Text(subtitle),
      dense: true,
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, this.details});

  final String message;
  final String? details;

  @override
  Widget build(BuildContext context) {
    final detailText = details?.trim();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            if (detailText != null && detailText.isNotEmpty) ...[
              const SizedBox(height: 6),
              SelectableText(detailText, style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

abstract interface class MusicArkBridgeClient {
  Future<Map<String, dynamic>> bootstrap();
  Future<Map<String, dynamic>> login(String token);
  Future<Map<String, dynamic>> refresh();
  Future<Map<String, dynamic>> logout();
}

class MusicArkBridge implements MusicArkBridgeClient {
  @override
  Future<Map<String, dynamic>> bootstrap() => _runBridge('bootstrap');

  @override
  Future<Map<String, dynamic>> login(String token) => _runBridge('login', token: token);

  @override
  Future<Map<String, dynamic>> refresh() => _runBridge('refresh');

  @override
  Future<Map<String, dynamic>> logout() => _runBridge('logout');

  Future<Map<String, dynamic>> _runBridge(String command, {String? token}) async {
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
    if (token != null && token.isNotEmpty) bridgeEnv['YANDEX_MUSIC_TOKEN'] = token;

    final result = await Process.run(
      python.executable,
      [
        ...python.prefixArgs,
        '-m',
        'musicark.mvp_bridge',
        '--base-dir',
        repoRoot,
        command,
      ],
      runInShell: false,
      workingDirectory: repoRoot,
      environment: bridgeEnv,
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
        (error['code'] ?? 'unexpected_error').toString(),
        (error['message'] ?? stderrText).toString(),
      );
    }
    if (result.exitCode != 0) {
      throw MusicArkBridgeException(
        'unexpected_error',
        stderrText.isNotEmpty ? stderrText : stdoutText,
      );
    }
    if (payload == null) {
      throw MusicArkBridgeException(
        'unexpected_error',
        stderrText.isNotEmpty ? stderrText : 'Bridge returned invalid JSON.',
      );
    }
    return payload;
  }

  String _resolveRepoRoot() {
    final override = Platform.environment['MUSICARK_REPO_ROOT']?.trim();
    if (override != null && override.isNotEmpty) {
      final directory = Directory(override);
      if (_looksLikeRepoRoot(directory)) return directory.absolute.path;
    }

    final candidates = <Directory>{
      Directory.current.absolute,
      File(Platform.resolvedExecutable).parent.absolute,
    };
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
        File('${directory.path}${separator}src${separator}musicark${separator}mvp_bridge.py')
            .existsSync();
  }

  Future<_PythonCommand> _resolvePythonCommand() async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) return _PythonCommand(override);

    final candidates = Platform.isWindows
        ? const [_PythonCommand('python'), _PythonCommand('py', prefixArgs: ['-3'])]
        : const [_PythonCommand('python3'), _PythonCommand('python')];

    for (final candidate in candidates) {
      try {
        final result = await Process.run(
          candidate.executable,
          [...candidate.prefixArgs, '--version'],
          runInShell: false,
        );
        if (result.exitCode == 0) return candidate;
      } on ProcessException {
        // Try the next known Python launcher.
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
  const FakeMusicArkBridge({this.startSignedIn = false});

  final bool startSignedIn;

  static const _account = {
    'provider': 'yandex_music',
    'providerUserId': 'test-user',
    'displayName': 'Tester',
  };

  static const _tracks = [
    {
      'provider_id': 'yandex_music',
      'external_id': '101',
      'title': 'Courtesy Call',
      'artists': ['Thousand Foot Krutch'],
      'album_title': 'The End Is Where We Begin',
    },
    {
      'provider_id': 'yandex_music',
      'external_id': '102',
      'title': 'Animal I Have Become',
      'artists': ['Three Days Grace'],
      'album_title': 'One-X',
    },
  ];

  Map<String, dynamic> _state({required bool signedIn, String source = 'network'}) => {
        'session': {
          'hasStoredToken': signedIn,
          'account': signedIn ? _account : <String, dynamic>{},
        },
        'library': {
          'source': signedIn ? source : 'none',
          'count': signedIn ? _tracks.length : 0,
          'lastUpdated': signedIn ? '2026-08-11T14:00:00+00:00' : null,
          'tracks': signedIn ? _tracks : <Map<String, dynamic>>[],
          'diff': {'added': 0, 'removed': 0, 'unchanged': signedIn ? _tracks.length : 0},
        },
      };

  @override
  Future<Map<String, dynamic>> bootstrap() async =>
      _state(signedIn: startSignedIn, source: 'cache');

  @override
  Future<Map<String, dynamic>> login(String token) async => _state(signedIn: true);

  @override
  Future<Map<String, dynamic>> refresh() async => _state(signedIn: true);

  @override
  Future<Map<String, dynamic>> logout() async => _state(signedIn: false, source: 'none');
}
