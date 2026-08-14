import 'package:flutter/material.dart';

import 'app_strings.dart';
import 'musicark_bridge.dart';

void main() => runApp(const MusicArkDesktopApp());

class MusicArkDesktopApp extends StatelessWidget {
  const MusicArkDesktopApp({super.key, this.bridge});

  final MusicArkBridgeClient? bridge;

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: AppStrings.appTitle,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
          useMaterial3: true,
        ),
        home: MusicArkHomePage(bridge: bridge ?? MusicArkBridge()),
      );
}

enum LibrarySort { original, title, artist }

enum PlaylistSort { original, title }

enum _PageKind { liked, playlists, playlist }

class MusicArkHomePage extends StatefulWidget {
  const MusicArkHomePage({super.key, required this.bridge});

  final MusicArkBridgeClient bridge;

  @override
  State<MusicArkHomePage> createState() => _MusicArkHomePageState();
}

class _MusicArkHomePageState extends State<MusicArkHomePage> {
  final _tokenController = TextEditingController();
  final _searchController = TextEditingController();

  bool _initializing = true;
  bool _busy = false;
  bool _tokenVisible = false;
  bool _hasStoredToken = false;
  String? _errorMessage;
  String? _errorDetails;
  Map<String, dynamic> _account = const {};
  List<Map<String, dynamic>> _likedTracks = const [];
  List<Map<String, dynamic>> _playlists = const [];
  List<Map<String, dynamic>> _playlistTracks = const [];
  Map<String, dynamic>? _selectedPlaylist;
  String _likedSource = 'none';
  String _playlistsSource = 'none';
  String _playlistSource = 'none';
  String? _likedLastUpdated;
  String? _playlistsLastUpdated;
  String? _playlistLastUpdated;
  LibrarySort _trackSort = LibrarySort.original;
  PlaylistSort _playlistSort = PlaylistSort.original;
  _PageKind _page = _PageKind.liked;

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
      _applyLibraryPayload(payload);
      setState(() => _initializing = false);
      if (_hasStoredToken) await _refreshLibrary(showDiff: false);
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      setState(() {
        _initializing = false;
        _setBridgeError(error);
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

    _beginBusy();
    try {
      final payload = await widget.bridge.login(token);
      if (!mounted) return;
      _applyLibraryPayload(payload);
      _tokenController.clear();
      _showDiff(_asMap(payload['liked'] ?? payload['library']));
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = AppStrings.unexpectedError;
          _errorDetails = error.toString();
        });
      }
    } finally {
      _endBusy();
    }
  }

  Future<void> _refreshLibrary({bool showDiff = true}) async {
    _beginBusy();
    try {
      final payload = await widget.bridge.libraryRefresh();
      if (!mounted) return;
      _applyLibraryPayload(payload);
      if (showDiff) {
        _showDiff(_asMap(payload['liked'] ?? payload['library']));
        _showDiff(_asMap(payload['playlists']));
      }
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } finally {
      _endBusy();
    }
  }

  Future<void> _refreshLiked() async {
    _beginBusy();
    try {
      final payload = await widget.bridge.likedRefresh();
      if (!mounted) return;
      _applyLibraryPayload(payload);
      _showDiff(_asMap(payload['liked'] ?? payload['library']));
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } finally {
      _endBusy();
    }
  }

  Future<void> _openPlaylist(Map<String, dynamic> playlist) async {
    final externalId = (playlist['externalId'] ?? '').toString();
    if (externalId.isEmpty) return;

    setState(() {
      _page = _PageKind.playlist;
      _selectedPlaylist = playlist;
      _playlistTracks = const [];
      _playlistSource = 'none';
      _playlistLastUpdated = null;
      _trackSort = LibrarySort.original;
      _searchController.clear();
      _errorMessage = null;
      _errorDetails = null;
    });

    try {
      final cached = await widget.bridge.playlist(externalId);
      if (!mounted || _selectedPlaylist?['externalId'] != externalId) return;
      _applyPlaylistPayload(cached);
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    }

    if (_hasStoredToken &&
        mounted &&
        _selectedPlaylist?['externalId'] == externalId) {
      await _refreshSelectedPlaylist(showDiff: false);
    }
  }

  Future<void> _refreshSelectedPlaylist({bool showDiff = true}) async {
    final externalId = (_selectedPlaylist?['externalId'] ?? '').toString();
    if (externalId.isEmpty) return;

    _beginBusy();
    try {
      final payload = await widget.bridge.playlistRefresh(externalId);
      if (!mounted || _selectedPlaylist?['externalId'] != externalId) return;
      _applyPlaylistPayload(payload);
      if (showDiff) _showDiff(_asMap(payload['collection']));
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } finally {
      _endBusy();
    }
  }

  Future<void> _logout() async {
    _beginBusy();
    try {
      final payload = await widget.bridge.logout();
      if (!mounted) return;
      _applyLibraryPayload(payload);
      setState(() {
        _page = _PageKind.liked;
        _selectedPlaylist = null;
        _playlistTracks = const [];
        _searchController.clear();
        _tokenController.clear();
        _trackSort = LibrarySort.original;
        _playlistSort = PlaylistSort.original;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } finally {
      _endBusy();
    }
  }

  void _beginBusy() {
    if (!mounted) return;
    setState(() {
      _busy = true;
      _errorMessage = null;
      _errorDetails = null;
    });
  }

  void _endBusy() {
    if (mounted) setState(() => _busy = false);
  }

  void _applyLibraryPayload(Map<String, dynamic> payload) {
    final session = _asMap(payload['session']);
    final liked = _asMap(payload['liked'] ?? payload['library']);
    final playlistIndex = _asMap(payload['playlists']);
    final playlistItems = _asListOfMaps(playlistIndex['items']);

    setState(() {
      _hasStoredToken = session['hasStoredToken'] == true;
      _account = _asMap(session['account']);
      _likedTracks = _asListOfMaps(liked['tracks']);
      _playlists = playlistItems;
      _likedSource = (liked['source'] ?? 'none').toString();
      _playlistsSource = (playlistIndex['source'] ?? 'none').toString();
      _likedLastUpdated = liked['lastUpdated']?.toString();
      _playlistsLastUpdated = playlistIndex['lastUpdated']?.toString();
      _errorMessage = null;
      _errorDetails = null;

      final selectedId = (_selectedPlaylist?['externalId'] ?? '').toString();
      if (selectedId.isNotEmpty &&
          !_playlists.any(
            (item) => (item['externalId'] ?? '').toString() == selectedId,
          )) {
        _selectedPlaylist = null;
        _playlistTracks = const [];
        if (_page == _PageKind.playlist) _page = _PageKind.playlists;
      } else if (selectedId.isNotEmpty) {
        final fresh = _playlists.firstWhere(
          (item) => (item['externalId'] ?? '').toString() == selectedId,
        );
        _selectedPlaylist = {...?_selectedPlaylist, ...fresh};
      }
    });
  }

  void _applyPlaylistPayload(Map<String, dynamic> payload) {
    final metadata = _asMap(payload['playlist']);
    final collection = _asMap(payload['collection']);
    setState(() {
      _selectedPlaylist = {...?_selectedPlaylist, ...metadata};
      _playlistTracks = _asListOfMaps(collection['tracks']);
      _playlistSource = (collection['source'] ?? 'none').toString();
      _playlistLastUpdated = collection['lastUpdated']?.toString();
      _errorMessage = null;
      _errorDetails = null;
    });
  }

  Map<String, dynamic> _asMap(dynamic value) =>
      value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

  List<Map<String, dynamic>> _asListOfMaps(dynamic value) => value is List
      ? value
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList(growable: false)
      : <Map<String, dynamic>>[];

  void _setBridgeError(MusicArkBridgeException error) {
    _errorMessage = _messageForBridgeError(error.code);
    _errorDetails = error.message;
  }

  String _messageForBridgeError(String code) => switch (code) {
        'token_missing' => AppStrings.tokenMissing,
        'authentication_failed' => AppStrings.authenticationFailed,
        'yandex_request_failed' => AppStrings.yandexRequestFailed,
        'credential_store_failed' => AppStrings.credentialStoreFailed,
        'cache_failed' => AppStrings.cacheFailed,
        'invalid_request' => AppStrings.invalidRequest,
        'python_not_found' => AppStrings.pythonNotFound,
        'repo_root_not_found' => AppStrings.repoRootNotFound,
        _ => AppStrings.unexpectedError,
      };

  void _showDiff(Map<String, dynamic> value) {
    if (!mounted) return;
    final diff = _asMap(value['diff']);
    final added = int.tryParse('${diff['added'] ?? 0}') ?? 0;
    final removed = int.tryParse('${diff['removed'] ?? 0}') ?? 0;
    if (added == 0 && removed == 0) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppStrings.syncDiff(added, removed))),
    );
  }

  void _showLiked() => setState(() {
        _page = _PageKind.liked;
        _searchController.clear();
        _trackSort = LibrarySort.original;
      });

  void _showPlaylists() => setState(() {
        _page = _PageKind.playlists;
        _searchController.clear();
        _playlistSort = PlaylistSort.original;
      });

  List<Map<String, dynamic>> get _visibleTracks {
    final source =
        _page == _PageKind.playlist ? _playlistTracks : _likedTracks;
    final query = _searchController.text.trim().toLowerCase();
    final filtered = source.where((track) {
      if (query.isEmpty) return true;
      final haystack = [
        (track['title'] ?? '').toString(),
        _artistsText(track),
        (track['album_title'] ?? '').toString(),
      ].join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList(growable: false);

    final sorted = List<Map<String, dynamic>>.from(filtered);
    if (_trackSort == LibrarySort.title) {
      sorted.sort(
        (a, b) => _title(a).toLowerCase().compareTo(_title(b).toLowerCase()),
      );
    }
    if (_trackSort == LibrarySort.artist) {
      sorted.sort(
        (a, b) =>
            _artistsText(a).toLowerCase().compareTo(_artistsText(b).toLowerCase()),
      );
    }
    return sorted;
  }

  List<Map<String, dynamic>> get _visiblePlaylists {
    final query = _searchController.text.trim().toLowerCase();
    final filtered = _playlists.where((playlist) {
      if (query.isEmpty) return true;
      return (playlist['title'] ?? '')
          .toString()
          .toLowerCase()
          .contains(query);
    }).toList(growable: false);

    final sorted = List<Map<String, dynamic>>.from(filtered);
    if (_playlistSort == PlaylistSort.title) {
      sorted.sort(
        (a, b) => (a['title'] ?? '')
            .toString()
            .toLowerCase()
            .compareTo((b['title'] ?? '').toString().toLowerCase()),
      );
    }
    return sorted;
  }

  String _title(Map<String, dynamic> track) =>
      (track['title'] ?? AppStrings.unknownTitle).toString().trim();

  String _artistsText(Map<String, dynamic> track) {
    final raw = track['artists'];
    if (raw is List) {
      final text = raw
          .map((value) => value.toString())
          .where((value) => value.isNotEmpty)
          .join(', ');
      if (text.isNotEmpty) return text;
    }
    final text = raw?.toString().trim() ?? '';
    return text.isEmpty ? AppStrings.unknownArtist : text;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('${AppStrings.appTitle} 0.3')),
        body: _initializing
            ? const Center(child: CircularProgressIndicator())
            : _hasStoredToken
                ? _buildSignedIn()
                : _buildLogin(),
      );

  Widget _buildLogin() => Center(
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
                    const Text(AppStrings.loginDescription),
                    const SizedBox(height: 20),
                    TextField(
                      key: const Key('token-field'),
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
                            _tokenVisible
                                ? Icons.visibility_off
                                : Icons.visibility,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    FilledButton(
                      key: const Key('login-button'),
                      onPressed: _busy ? null : _signIn,
                      child: Text(
                        _busy ? AppStrings.signingIn : AppStrings.signIn,
                      ),
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

  Widget _buildSignedIn() => Row(
        children: [
          _buildSidebar(),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                if (_busy) const LinearProgressIndicator(),
                if (_errorMessage != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                    child: _ErrorPanel(
                      message: _errorMessage!,
                      details: _errorDetails,
                    ),
                  ),
                Expanded(child: _buildPage()),
              ],
            ),
          ),
        ],
      );

  Widget _buildSidebar() {
    final displayName =
        (_account['displayName'] ?? _account['providerUserId'] ?? '').toString();

    return SizedBox(
      key: const Key('library-sidebar'),
      width: 280,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  AppStrings.yandexMusic,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                if (displayName.isNotEmpty)
                  Text(
                    displayName,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
          ListTile(
            key: const Key('nav-liked'),
            leading: const Icon(Icons.favorite_outline),
            selected: _page == _PageKind.liked,
            title: const Text(AppStrings.likedTracks),
            onTap: _showLiked,
          ),
          ListTile(
            key: const Key('nav-playlists'),
            leading: const Icon(Icons.queue_music),
            selected: _page == _PageKind.playlists,
            title: const Text(AppStrings.playlists),
            trailing: Text('${_playlists.length}'),
            onTap: _showPlaylists,
          ),
          if (_playlists.isNotEmpty) const Divider(),
          Expanded(
            child: ListView.builder(
              itemCount: _playlists.length,
              itemBuilder: (context, index) {
                final item = _playlists[index];
                final id = (item['externalId'] ?? '').toString();
                return ListTile(
                  key: Key('nav-playlist-$id'),
                  contentPadding: const EdgeInsets.only(left: 40, right: 12),
                  dense: true,
                  selected: _page == _PageKind.playlist &&
                      _selectedPlaylist?['externalId'] == id,
                  title: Text(
                    (item['title'] ?? AppStrings.unknownPlaylist).toString(),
                  ),
                  onTap: () => _openPlaylist(item),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                FilledButton.tonalIcon(
                  key: const Key('refresh-library'),
                  onPressed: _busy ? null : _refreshLibrary,
                  icon: const Icon(Icons.sync),
                  label: const Text(AppStrings.refreshLibrary),
                ),
                const SizedBox(height: 6),
                TextButton(
                  key: const Key('logout-button'),
                  onPressed: _busy ? null : _logout,
                  child: const Text(AppStrings.logout),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPage() => switch (_page) {
        _PageKind.liked => _buildTrackCollection(
            title: AppStrings.likedTracks,
            tracks: _likedTracks,
            source: _likedSource,
            lastUpdated: _likedLastUpdated,
            emptyMessage: AppStrings.emptyLikes,
            refresh: _refreshLiked,
          ),
        _PageKind.playlists => _buildPlaylistIndex(),
        _PageKind.playlist => _buildTrackCollection(
            title: (_selectedPlaylist?['title'] ?? AppStrings.unknownPlaylist)
                .toString(),
            tracks: _playlistTracks,
            source: _playlistSource,
            lastUpdated: _playlistLastUpdated,
            emptyMessage: AppStrings.emptyPlaylist,
            refresh: _refreshSelectedPlaylist,
            subtitle: _playlistSubtitle(_selectedPlaylist),
          ),
      };

  Widget _buildTrackCollection({
    required String title,
    required List<Map<String, dynamic>> tracks,
    required String source,
    required String? lastUpdated,
    required String emptyMessage,
    required Future<void> Function() refresh,
    String? subtitle,
  }) {
    final visible = _visibleTracks;

    return Column(
      children: [
        _CollectionHeader(
          title: title,
          subtitle: subtitle,
          source: source,
          lastUpdated: lastUpdated,
          countLabel: visible.length == tracks.length
              ? AppStrings.trackCount(tracks.length)
              : AppStrings.filteredCount(visible.length, tracks.length),
          onRefresh: _busy ? null : refresh,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('track-search'),
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
                width: 280,
                child: DropdownButtonFormField<LibrarySort>(
                  key: Key('track-sort-${_trackSort.name}'),
                  initialValue: _trackSort,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: AppStrings.sort,
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: LibrarySort.original,
                      child: Text(AppStrings.sortOriginal),
                    ),
                    DropdownMenuItem(
                      value: LibrarySort.title,
                      child: Text(AppStrings.sortTitle),
                    ),
                    DropdownMenuItem(
                      value: LibrarySort.artist,
                      child: Text(AppStrings.sortArtist),
                    ),
                  ],
                  onChanged: _busy
                      ? null
                      : (value) {
                          if (value != null) {
                            setState(() => _trackSort = value);
                          }
                        },
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: visible.isEmpty
              ? Center(
                  child: Text(
                    tracks.isEmpty
                        ? emptyMessage
                        : AppStrings.noSearchResults,
                  ),
                )
              : ListView.separated(
                  key: const Key('track-list'),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: visible.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, index) =>
                      _TrackTile(track: visible[index]),
                ),
        ),
      ],
    );
  }

  Widget _buildPlaylistIndex() {
    final visible = _visiblePlaylists;

    return Column(
      children: [
        _CollectionHeader(
          title: AppStrings.playlists,
          source: _playlistsSource,
          lastUpdated: _playlistsLastUpdated,
          countLabel: visible.length == _playlists.length
              ? AppStrings.playlistCount(_playlists.length)
              : AppStrings.filteredCount(visible.length, _playlists.length),
          onRefresh: _busy ? null : _refreshLibrary,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('playlist-search'),
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(
                    labelText: AppStrings.playlistSearch,
                    prefixIcon: Icon(Icons.search),
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 280,
                child: DropdownButtonFormField<PlaylistSort>(
                  key: Key('playlist-sort-${_playlistSort.name}'),
                  initialValue: _playlistSort,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: AppStrings.sort,
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: PlaylistSort.original,
                      child: Text(AppStrings.sortOriginal),
                    ),
                    DropdownMenuItem(
                      value: PlaylistSort.title,
                      child: Text(AppStrings.sortTitle),
                    ),
                  ],
                  onChanged: _busy
                      ? null
                      : (value) {
                          if (value != null) {
                            setState(() => _playlistSort = value);
                          }
                        },
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: visible.isEmpty
              ? Center(
                  child: Text(
                    _playlists.isEmpty
                        ? AppStrings.emptyPlaylists
                        : AppStrings.noSearchResults,
                  ),
                )
              : ListView.separated(
                  key: const Key('playlist-list'),
                  itemCount: visible.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final item = visible[index];
                    final id = (item['externalId'] ?? '').toString();
                    final owner = (item['ownerName'] ?? '').toString();
                    final count =
                        int.tryParse('${item['trackCount'] ?? 0}') ?? 0;
                    final updated = item['lastUpdated']?.toString() ??
                        AppStrings.neverUpdated;
                    return ListTile(
                      key: Key('playlist-row-$id'),
                      leading: const Icon(Icons.queue_music),
                      title: Text(
                        (item['title'] ?? AppStrings.unknownPlaylist).toString(),
                      ),
                      subtitle: Text(
                        [
                          if (owner.isNotEmpty) owner,
                          AppStrings.externalId(id),
                          AppStrings.lastUpdated(updated),
                        ].join(' · '),
                      ),
                      trailing: Text(AppStrings.trackCount(count)),
                      onTap: () => _openPlaylist(item),
                    );
                  },
                ),
        ),
      ],
    );
  }

  String? _playlistSubtitle(Map<String, dynamic>? playlist) {
    if (playlist == null) return null;
    final values = <String>[];
    final owner = (playlist['ownerName'] ?? '').toString();
    final id = (playlist['externalId'] ?? '').toString();
    if (owner.isNotEmpty) values.add(owner);
    if (id.isNotEmpty) values.add(AppStrings.externalId(id));
    return values.isEmpty ? null : values.join(' · ');
  }
}

class _CollectionHeader extends StatelessWidget {
  const _CollectionHeader({
    required this.title,
    required this.source,
    required this.lastUpdated,
    required this.countLabel,
    required this.onRefresh,
    this.subtitle,
  });

  final String title;
  final String? subtitle;
  final String source;
  final String? lastUpdated;
  final String countLabel;
  final VoidCallback? onRefresh;

  @override
  Widget build(BuildContext context) {
    final sourceLabel = switch (source) {
      'network' => AppStrings.networkSource,
      'cache' => AppStrings.cacheSource,
      _ => AppStrings.noneSource,
    };
    final titleChildren = <Widget>[
      Text(title, style: Theme.of(context).textTheme.headlineSmall),
    ];
    final subtitleText = subtitle?.trim();
    if (subtitleText != null && subtitleText.isNotEmpty) {
      titleChildren.add(Text(subtitleText));
    }
    titleChildren.add(
      Text(
        AppStrings.lastUpdated(lastUpdated ?? AppStrings.neverUpdated),
        style: Theme.of(context).textTheme.bodySmall,
      ),
    );

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: titleChildren,
            ),
          ),
          Chip(label: Text(sourceLabel)),
          const SizedBox(width: 12),
          Text(countLabel),
          const SizedBox(width: 8),
          IconButton(
            key: const Key('refresh-current'),
            tooltip: AppStrings.refresh,
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
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
    final duration = _formatDuration(track['duration_seconds']);
    final availability = (track['availability'] ?? '').toString().trim();

    return ListTile(
      leading: const Icon(Icons.music_note),
      title: Text(title.isEmpty ? AppStrings.unknownTitle : title),
      subtitle: Text(
        [
          artists.isEmpty ? AppStrings.unknownArtist : artists,
          if (album.isNotEmpty) album,
          if (duration != null) duration,
          if (availability.isNotEmpty) availability,
        ].join(' · '),
      ),
      dense: true,
    );
  }

  static String? _formatDuration(dynamic raw) {
    final seconds = raw is int ? raw : int.tryParse('${raw ?? ''}');
    if (seconds == null || seconds < 0) return null;
    return '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, this.details});

  final String message;
  final String? details;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[
      Text(
        message,
        style: TextStyle(color: Theme.of(context).colorScheme.error),
      ),
    ];
    final detailText = details?.trim();
    if (detailText != null && detailText.isNotEmpty) {
      children.add(const SizedBox(height: 6));
      children.add(
        SelectableText(
          detailText,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }

    return Card(
      key: const Key('error-panel'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: children,
        ),
      ),
    );
  }
}
