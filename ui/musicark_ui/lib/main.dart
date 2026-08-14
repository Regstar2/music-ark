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

class MusicArkHomePage extends StatefulWidget {
  const MusicArkHomePage({super.key, required this.bridge});

  final MusicArkBridgeClient bridge;

  @override
  State<MusicArkHomePage> createState() => _MusicArkHomePageState();
}

class _MusicArkHomePageState extends State<MusicArkHomePage> {
  final TextEditingController _tokenController = TextEditingController();

  bool _busy = false;
  bool _tokenVisible = false;
  String? _sessionToken;
  String? _errorMessage;
  String? _errorDetails;
  Map<String, dynamic>? _account;
  List<Map<String, dynamic>> _tracks = const [];

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
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
      final account = await widget.bridge.login(token);
      final likes = await widget.bridge.likes(token);
      final tracks = _parseTracks(likes);

      if (!mounted) return;
      setState(() {
        _sessionToken = token;
        _account = account;
        _tracks = tracks;
        _tokenController.clear();
      });
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

  Future<void> _refreshLikes() async {
    final token = _sessionToken;
    if (token == null || token.isEmpty) return;

    setState(() {
      _busy = true;
      _errorMessage = null;
      _errorDetails = null;
    });

    try {
      final likes = await widget.bridge.likes(token);
      if (mounted) setState(() => _tracks = _parseTracks(likes));
    } on MusicArkBridgeException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = _messageForBridgeError(error.code);
          _errorDetails = error.message;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = AppStrings.unexpectedError;
          _errorDetails = error.toString();
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  List<Map<String, dynamic>> _parseTracks(Map<String, dynamic> likes) {
    final rawTracks = likes['tracks'];
    if (rawTracks is! List) return const [];
    return rawTracks
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  void _logout() {
    setState(() {
      _sessionToken = null;
      _account = null;
      _tracks = const [];
      _errorMessage = null;
      _errorDetails = null;
      _tokenController.clear();
    });
  }

  String _messageForBridgeError(String code) {
    switch (code) {
      case 'token_missing':
        return AppStrings.tokenMissing;
      case 'authentication_failed':
        return AppStrings.authenticationFailed;
      case 'yandex_request_failed':
        return AppStrings.yandexRequestFailed;
      case 'python_not_found':
        return AppStrings.pythonNotFound;
      case 'repo_root_not_found':
        return AppStrings.repoRootNotFound;
      default:
        return AppStrings.unexpectedError;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text(AppStrings.appTitle)),
      body: _account == null ? _buildLogin() : _buildLikes(),
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
                  Text(
                    AppStrings.loginTitle,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 12),
                  Text(AppStrings.loginDescription),
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
                            : () => setState(
                                  () => _tokenVisible = !_tokenVisible,
                                ),
                        icon: Icon(
                          _tokenVisible ? Icons.visibility_off : Icons.visibility,
                        ),
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
                    _ErrorPanel(
                      message: _errorMessage!,
                      details: _errorDetails,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLikes() {
    final displayName =
        (_account?['displayName'] ?? _account?['providerUserId'] ?? '').toString();

    return Column(
      children: [
        Material(
          elevation: 1,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        AppStrings.likedTracks,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      if (displayName.isNotEmpty) Text(displayName),
                    ],
                  ),
                ),
                Text(AppStrings.trackCount(_tracks.length)),
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
          ),
        ),
        if (_errorMessage != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            child: _ErrorPanel(
              message: _errorMessage!,
              details: _errorDetails,
            ),
          ),
        Expanded(
          child: _busy
              ? const Center(child: CircularProgressIndicator())
              : _tracks.isEmpty
                  ? const Center(child: Text(AppStrings.emptyLikes))
                  : ListView.separated(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      itemCount: _tracks.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, index) =>
                          _TrackTile(track: _tracks[index]),
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
    final subtitleParts = <String>[
      if (artists.isNotEmpty) artists else AppStrings.unknownArtist,
      if (album.isNotEmpty) album,
    ];

    return ListTile(
      leading: const Icon(Icons.music_note),
      title: Text(title.isEmpty ? AppStrings.unknownTitle : title),
      subtitle: Text(subtitleParts.join(' · ')),
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
            Text(
              message,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            if (detailText != null && detailText.isNotEmpty) ...[
              const SizedBox(height: 6),
              SelectableText(
                detailText,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

abstract interface class MusicArkBridgeClient {
  Future<Map<String, dynamic>> login(String token);
  Future<Map<String, dynamic>> likes(String token);
}

class MusicArkBridge implements MusicArkBridgeClient {
  @override
  Future<Map<String, dynamic>> login(String token) => _runBridge('login', token);

  @override
  Future<Map<String, dynamic>> likes(String token) => _runBridge('likes', token);

  Future<Map<String, dynamic>> _runBridge(String command, String token) async {
    final repoRoot = _resolveRepoRoot();
    final python = await _resolvePythonCommand();
    final srcPath = '$repoRoot${Platform.pathSeparator}src';
    final existingPythonPath = Platform.environment['PYTHONPATH'];
    final mergedPythonPath =
        existingPythonPath == null || existingPythonPath.isEmpty
            ? srcPath
            : '$srcPath${Platform.isWindows ? ';' : ':'}$existingPythonPath';

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
      environment: {
        ...Platform.environment,
        'PYTHONPATH': mergedPythonPath,
        'PYTHONIOENCODING': 'utf-8',
        'PYTHONUTF8': '1',
        'YANDEX_MUSIC_TOKEN': token,
      },
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
    throw const MusicArkBridgeException(
      'repo_root_not_found',
      AppStrings.repoRootNotFound,
    );
  }

  bool _looksLikeRepoRoot(Directory directory) {
    final separator = Platform.pathSeparator;
    return File('${directory.path}${separator}pyproject.toml').existsSync() &&
        File(
          '${directory.path}${separator}src${separator}musicark${separator}mvp_bridge.py',
        ).existsSync();
  }

  Future<_PythonCommand> _resolvePythonCommand() async {
    final override = Platform.environment['MUSICARK_PYTHON']?.trim();
    if (override != null && override.isNotEmpty) return _PythonCommand(override);

    final candidates = Platform.isWindows
        ? const [
            _PythonCommand('python'),
            _PythonCommand('py', prefixArgs: ['-3']),
          ]
        : const [
            _PythonCommand('python3'),
            _PythonCommand('python'),
          ];

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
    throw const MusicArkBridgeException(
      'python_not_found',
      AppStrings.pythonNotFound,
    );
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
  const FakeMusicArkBridge({
    this.account = const {
      'provider': 'yandex_music',
      'providerUserId': 'test-user',
      'displayName': 'Tester',
    },
    this.tracks = const [
      {
        'provider_id': 'yandex_music',
        'external_id': '101',
        'title': 'Courtesy Call',
        'artists': ['Thousand Foot Krutch'],
        'album_title': 'The End Is Where We Begin',
      },
    ],
  });

  final Map<String, dynamic> account;
  final List<Map<String, dynamic>> tracks;

  @override
  Future<Map<String, dynamic>> login(String token) async => account;

  @override
  Future<Map<String, dynamic>> likes(String token) async => {
        'count': tracks.length,
        'tracks': tracks,
      };
}
