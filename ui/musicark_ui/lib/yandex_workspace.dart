import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'app_localizations_ext.dart';
import 'app_theme.dart';
import 'app_ui_tokens.dart';
import 'audio_player.dart';
import 'content_label_bridge.dart';
import 'l10n/app_localizations.dart';
import 'musicark_bridge.dart';
import 'yandex_content_labels.dart';

enum LibrarySort { original, title, artist, unavailable }
enum PlaylistSort { original, title }
enum _PageKind { liked, playlists, albums, playlist, album }

Locale resolveYandexLocale(Locale? locale) {
  final language = locale?.languageCode.toLowerCase();
  return language == 'en' ? const Locale('en') : const Locale('ru');
}

/// Standalone Yandex workspace retained for development and focused widget tests.
class MusicArkDesktopApp extends StatelessWidget {
  const MusicArkDesktopApp({
    super.key,
    this.bridge,
    this.contentLabelBridge,
    this.locale,
  });

  final MusicArkBridgeClient? bridge;
  final ContentLabelBridgeClient? contentLabelBridge;
  final Locale? locale;

  @override
  Widget build(BuildContext context) {
    final client = bridge ?? MusicArkBridge();
    final labels = contentLabelBridge ??
        (bridge == null ? const ContentLabelBridge() : null);
    final effectiveLocale = locale ??
        resolveYandexLocale(WidgetsBinding.instance.platformDispatcher.locale);
    return MaterialApp(
      locale: effectiveLocale,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: MusicArkHomePage(bridge: client, contentLabelBridge: labels),
    );
  }
}

class MusicArkHomePage extends StatefulWidget {
  const MusicArkHomePage({
    super.key,
    required this.bridge,
    this.contentLabelBridge,
  });

  final MusicArkBridgeClient bridge;
  final ContentLabelBridgeClient? contentLabelBridge;

  @override
  State<MusicArkHomePage> createState() => _MusicArkHomePageState();
}

class _MusicArkHomePageState extends State<MusicArkHomePage> {
  static const _trackSearchDelay = Duration(milliseconds: 180);

  final _tokenController = TextEditingController();
  final _searchController = TextEditingController();

  bool _initializing = true;
  bool _busy = false;
  bool _tokenVisible = false;
  bool _hasStoredToken = false;
  String? _errorMessage;
  String? _errorDetails;
  List<Map<String, dynamic>> _likedTracks = const [];
  List<Map<String, dynamic>> _playlists = const [];
  List<Map<String, dynamic>> _likedAlbums = const [];
  List<Map<String, dynamic>> _detailTracks = const [];
  Map<String, dynamic>? _selectedPlaylist;
  Map<String, dynamic>? _selectedAlbum;
  Map<String, String> _contentLabels = const {};
  String? _playingTrackId;
  String _likedSource = 'none';
  String _playlistsSource = 'none';
  String _albumsSource = 'none';
  String _detailSource = 'none';
  String? _likedLastUpdated;
  String? _playlistsLastUpdated;
  String? _albumsLastUpdated;
  String? _detailLastUpdated;
  LibrarySort _trackSort = LibrarySort.original;
  PlaylistSort _playlistSort = PlaylistSort.original;
  _PageKind _page = _PageKind.liked;
  Timer? _trackSearchDebounce;
  String _trackSearchQuery = '';
  List<Map<String, dynamic>>? _visibleTrackCache;
  List<Map<String, dynamic>>? _visibleTrackCacheSource;
  String _visibleTrackCacheQuery = '';
  LibrarySort? _visibleTrackCacheSort;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  @override
  void dispose() {
    _trackSearchDebounce?.cancel();
    _tokenController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _maps(dynamic value) => value is List
      ? value
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList()
      : <Map<String, dynamic>>[];

  Map<String, dynamic> _map(dynamic value) =>
      value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

  String _id(Map<String, dynamic> item) =>
      '${item['external_id'] ?? item['externalId'] ?? ''}'.trim();

  String _title(Map<String, dynamic> track) {
    final value = '${track['title'] ?? ''}'.trim();
    return value.isEmpty ? context.l10n.yandexUnknownTitle : value;
  }

  String _artists(Map<String, dynamic> item) {
    final raw = item['artists'];
    if (raw is List) {
      final value = raw
          .map((entry) => '$entry'.trim())
          .where((entry) => entry.isNotEmpty)
          .join(', ');
      if (value.isNotEmpty) return value;
    }
    final value = '${raw ?? ''}'.trim();
    return value.isEmpty ? context.l10n.yandexUnknownArtist : value;
  }

  void _invalidateVisibleTracks() {
    _visibleTrackCache = null;
    _visibleTrackCacheSource = null;
    _visibleTrackCacheQuery = '';
    _visibleTrackCacheSort = null;
  }

  void _resetTrackSearch() {
    _trackSearchDebounce?.cancel();
    _searchController.clear();
    _trackSearchQuery = '';
    _invalidateVisibleTracks();
  }

  void _scheduleTrackSearch(String value) {
    final query = value.trim().toLowerCase();
    _trackSearchDebounce?.cancel();
    _trackSearchDebounce = Timer(_trackSearchDelay, () {
      if (!mounted || query == _trackSearchQuery) return;
      setState(() {
        _trackSearchQuery = query;
        _invalidateVisibleTracks();
      });
    });
  }

  void _submitTrackSearch(String value) {
    final query = value.trim().toLowerCase();
    _trackSearchDebounce?.cancel();
    if (query == _trackSearchQuery) return;
    setState(() {
      _trackSearchQuery = query;
      _invalidateVisibleTracks();
    });
  }

  Future<void> _initialize() async {
    try {
      final payload = await widget.bridge.bootstrap();
      if (!mounted) return;
      _applyLibrary(payload);
      await _loadLabels(_likedTracks);
      if (!mounted) return;
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
        _errorMessage = context.l10n.yandexUnexpectedError;
        _errorDetails = error.toString();
      });
    }
  }

  void _applyLibrary(Map<String, dynamic> payload) {
    final session = _map(payload['session']);
    final liked = _map(payload['liked'] ?? payload['library']);
    final playlists = _map(payload['playlists']);
    final albums = _map(payload['albums']);
    setState(() {
      _hasStoredToken = session['hasStoredToken'] == true;
      _likedTracks = _maps(liked['tracks']);
      _playlists = _maps(playlists['items']);
      _likedAlbums = _maps(albums['items']);
      _likedSource = '${liked['source'] ?? 'none'}';
      _playlistsSource = '${playlists['source'] ?? 'none'}';
      _albumsSource = '${albums['source'] ?? 'none'}';
      _likedLastUpdated = liked['lastUpdated']?.toString();
      _playlistsLastUpdated = playlists['lastUpdated']?.toString();
      _albumsLastUpdated = albums['lastUpdated']?.toString();
      _invalidateVisibleTracks();
      _errorMessage = null;
      _errorDetails = null;
    });
  }

  Future<void> _loadLabels(List<Map<String, dynamic>> tracks) async {
    final labels = widget.contentLabelBridge;
    if (labels == null) return;
    final ids = tracks
        .map(_id)
        .where((id) => id.isNotEmpty)
        .toList(growable: false);
    try {
      final payload = await labels.batch(externalIds: ids);
      final raw = payload['provider'];
      if (!mounted) return;
      setState(() {
        _contentLabels = raw is Map
            ? raw.map((key, value) => MapEntry('$key', '$value'))
            : <String, String>{};
      });
    } on MusicArkBridgeException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = context.l10n.yandexContentLabelsLoadFailed;
        _errorDetails = error.message;
      });
    }
  }

  void _beginBusy() => setState(() => _busy = true);

  void _endBusy() {
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _signIn() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      setState(() => _errorMessage = context.l10n.yandexTokenRequired);
      return;
    }
    _beginBusy();
    try {
      final payload = await widget.bridge.login(token);
      if (!mounted) return;
      _applyLibrary(payload);
      await _loadLabels(_likedTracks);
      _tokenController.clear();
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } finally {
      _endBusy();
    }
  }

  Future<void> _refreshLibrary({bool showDiff = true}) async {
    _beginBusy();
    try {
      final payload = await widget.bridge.libraryRefresh();
      if (!mounted) return;
      _applyLibrary(payload);
      await _loadLabels(_likedTracks);
      if (showDiff) {
        _showDiff(_map(payload['liked'] ?? payload['library']));
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
      _applyLibrary(payload);
      await _loadLabels(_likedTracks);
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    } finally {
      _endBusy();
    }
  }

  Future<void> _openPlaylist(Map<String, dynamic> playlist) async {
    final externalId = _id(playlist);
    if (externalId.isEmpty) return;
    setState(() {
      _selectedPlaylist = playlist;
      _detailTracks = const [];
      _detailSource = 'none';
      _detailLastUpdated = null;
      _page = _PageKind.playlist;
      _resetTrackSearch();
      _trackSort = LibrarySort.original;
    });
    try {
      _applyDetail(
        await widget.bridge.playlist(externalId),
        kind: _PageKind.playlist,
      );
      if (_hasStoredToken) {
        _applyDetail(
          await widget.bridge.playlistRefresh(externalId),
          kind: _PageKind.playlist,
        );
      }
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    }
  }

  Future<void> _openAlbum(Map<String, dynamic> album) async {
    final externalId = _id(album);
    if (externalId.isEmpty) return;
    setState(() {
      _selectedAlbum = album;
      _detailTracks = const [];
      _detailSource = 'none';
      _detailLastUpdated = null;
      _page = _PageKind.album;
      _resetTrackSearch();
      _trackSort = LibrarySort.original;
    });
    try {
      _applyDetail(
        await widget.bridge.album(externalId),
        kind: _PageKind.album,
      );
      if (_hasStoredToken) {
        _applyDetail(
          await widget.bridge.albumRefresh(externalId),
          kind: _PageKind.album,
        );
      }
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    }
  }

  void _applyDetail(
    Map<String, dynamic> payload, {
    required _PageKind kind,
  }) {
    if (!mounted) return;
    final collection = _map(payload['collection']);
    final metadata = _map(
      kind == _PageKind.album ? payload['album'] : payload['playlist'],
    );
    setState(() {
      if (kind == _PageKind.album) {
        _selectedAlbum = {...?_selectedAlbum, ...metadata};
      } else {
        _selectedPlaylist = {...?_selectedPlaylist, ...metadata};
      }
      _detailTracks = _maps(collection['tracks']);
      _detailSource = '${collection['source'] ?? 'none'}';
      _detailLastUpdated = collection['lastUpdated']?.toString();
      _invalidateVisibleTracks();
      _errorMessage = null;
      _errorDetails = null;
    });
    _loadLabels(_detailTracks);
  }

  Future<void> _refreshDetail() async {
    try {
      if (_page == _PageKind.album) {
        final id = _selectedAlbum == null ? '' : _id(_selectedAlbum!);
        if (id.isNotEmpty) {
          _applyDetail(
            await widget.bridge.albumRefresh(id),
            kind: _PageKind.album,
          );
        }
      } else {
        final id = _selectedPlaylist == null ? '' : _id(_selectedPlaylist!);
        if (id.isNotEmpty) {
          _applyDetail(
            await widget.bridge.playlistRefresh(id),
            kind: _PageKind.playlist,
          );
        }
      }
    } on MusicArkBridgeException catch (error) {
      if (mounted) setState(() => _setBridgeError(error));
    }
  }

  void _setBridgeError(MusicArkBridgeException error) {
    final l10n = context.l10n;
    _errorMessage = switch (error.code) {
      'token_missing' => l10n.yandexTokenMissing,
      'authentication_failed' => l10n.yandexAuthenticationFailed,
      'yandex_request_failed' => l10n.yandexRequestFailed,
      'credential_store_failed' => l10n.yandexCredentialStoreFailed,
      'cache_failed' => l10n.yandexCacheFailed,
      'invalid_request' => l10n.yandexInvalidRequest,
      'python_not_found' => l10n.yandexPythonNotFound,
      'repo_root_not_found' => l10n.yandexRepoRootNotFound,
      _ => l10n.yandexUnexpectedError,
    };
    _errorDetails = error.message;
  }

  void _showDiff(Map<String, dynamic> payload) {
    final diff = _map(payload['diff']);
    final added = int.tryParse('${diff['added'] ?? 0}') ?? 0;
    final removed = int.tryParse('${diff['removed'] ?? 0}') ?? 0;
    if ((added == 0 && removed == 0) || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '${context.l10n.yandexUpdatedPrefix}: +$added / -$removed',
        ),
      ),
    );
  }

  Future<void> _setLabel(Map<String, dynamic> track, String label) async {
    final bridge = widget.contentLabelBridge;
    final externalId = _id(track);
    if (bridge == null || externalId.isEmpty) return;
    try {
      await bridge.setProvider(externalId, label);
      if (!mounted) return;
      setState(() {
        final values = Map<String, String>.from(_contentLabels);
        if (label.isEmpty) {
          values.remove(externalId);
        } else {
          values[externalId] = label;
        }
        _contentLabels = values;
      });
    } on MusicArkBridgeException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = context.l10n.yandexContentLabelUpdateFailed;
          _errorDetails = error.message;
        });
      }
    }
  }

  Future<void> _play(Map<String, dynamic> track) async {
    final externalId = _id(track);
    if (externalId.isEmpty) return;
    setState(() => _playingTrackId = externalId);
    try {
      final prepared = await widget.bridge.yandexPlaybackPrepare(externalId);
      final path = '${prepared['path'] ?? ''}'.trim();
      await MusicArkAudioPlayer.instance.open(
        path,
        title: '${_artists(track)} — ${_title(track)}',
      );
    } catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = context.l10n.yandexPlaybackFailed;
          _errorDetails = error.toString();
        });
      }
    } finally {
      if (mounted) setState(() => _playingTrackId = null);
    }
  }

  void _showLiked() {
    setState(() {
      _page = _PageKind.liked;
      _resetTrackSearch();
      _trackSort = LibrarySort.original;
    });
  }

  void _showPlaylists() {
    _trackSearchDebounce?.cancel();
    setState(() {
      _page = _PageKind.playlists;
      _searchController.clear();
      _trackSearchQuery = '';
      _invalidateVisibleTracks();
      _playlistSort = PlaylistSort.original;
    });
  }

  void _showAlbums() {
    _trackSearchDebounce?.cancel();
    setState(() {
      _page = _PageKind.albums;
      _searchController.clear();
      _trackSearchQuery = '';
      _invalidateVisibleTracks();
    });
  }

  List<Map<String, dynamic>> get _trackSource =>
      _page == _PageKind.liked ? _likedTracks : _detailTracks;

  List<Map<String, dynamic>> get _visibleTracks {
    final source = _trackSource;
    final query = _trackSearchQuery;
    if (query.isEmpty && _trackSort == LibrarySort.original) return source;
    if (identical(_visibleTrackCacheSource, source) &&
        _visibleTrackCacheQuery == query &&
        _visibleTrackCacheSort == _trackSort &&
        _visibleTrackCache != null) {
      return _visibleTrackCache!;
    }

    final filtered = query.isEmpty
        ? source.toList(growable: false)
        : source.where((track) {
            return '${track['title'] ?? ''} ${_artists(track)} ${track['album_title'] ?? ''}'
                .toLowerCase()
                .contains(query);
          }).toList(growable: false);
    final indexed = filtered.asMap().entries.toList();
    switch (_trackSort) {
      case LibrarySort.original:
        break;
      case LibrarySort.title:
        indexed.sort((a, b) {
          final result = _title(a.value)
              .toLowerCase()
              .compareTo(_title(b.value).toLowerCase());
          return result == 0 ? a.key.compareTo(b.key) : result;
        });
      case LibrarySort.artist:
        indexed.sort((a, b) {
          final result = _artists(a.value)
              .toLowerCase()
              .compareTo(_artists(b.value).toLowerCase());
          return result == 0 ? a.key.compareTo(b.key) : result;
        });
      case LibrarySort.unavailable:
        indexed.sort((a, b) {
          final aUnavailable = '${a.value['availability'] ?? ''}' == 'unavailable';
          final bUnavailable = '${b.value['availability'] ?? ''}' == 'unavailable';
          if (aUnavailable != bUnavailable) return aUnavailable ? -1 : 1;
          return a.key.compareTo(b.key);
        });
    }
    final result = indexed.map((entry) => entry.value).toList(growable: false);
    _visibleTrackCacheSource = source;
    _visibleTrackCacheQuery = query;
    _visibleTrackCacheSort = _trackSort;
    _visibleTrackCache = result;
    return result;
  }

  List<Map<String, dynamic>> get _visiblePlaylists {
    final query = _searchController.text.trim().toLowerCase();
    final values = _playlists
        .where(
          (item) =>
              query.isEmpty ||
              '${item['title'] ?? ''}'.toLowerCase().contains(query),
        )
        .toList();
    if (_playlistSort == PlaylistSort.title) {
      values.sort(
        (a, b) => '${a['title'] ?? ''}'
            .toLowerCase()
            .compareTo('${b['title'] ?? ''}'.toLowerCase()),
      );
    }
    return values;
  }

  List<Map<String, dynamic>> get _visibleAlbums {
    final query = _searchController.text.trim().toLowerCase();
    return _likedAlbums
        .where(
          (album) =>
              query.isEmpty ||
              '${album['title'] ?? ''} ${_artists(album)}'
                  .toLowerCase()
                  .contains(query),
        )
        .toList(growable: false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: _initializing
            ? const Center(child: CircularProgressIndicator())
            : _hasStoredToken
                ? _buildSignedIn()
                : _buildLogin(),
      );

  Widget _buildLogin() {
    final l10n = context.l10n;
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
                    l10n.yandexLoginTitle,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 12),
                  Text(l10n.yandexLoginDescription),
                  const SizedBox(height: 20),
                  TextField(
                    key: const Key('token-field'),
                    controller: _tokenController,
                    obscureText: !_tokenVisible,
                    enabled: !_busy,
                    decoration: InputDecoration(
                      labelText: l10n.yandexTokenLabel,
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
                      _busy ? l10n.yandexSigningIn : l10n.signIn,
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
  }

  Widget _buildSignedIn() => Column(
        children: [
          if (_busy) const LinearProgressIndicator(),
          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 0),
              child: _ErrorPanel(
                message: _errorMessage!,
                details: _errorDetails,
              ),
            ),
          Expanded(
            child: switch (_page) {
              _PageKind.liked => _buildTrackCollection(
                  context.l10n.yandexLikedTitle,
                  _likedTracks,
                  _likedSource,
                  _likedLastUpdated,
                  _refreshLiked,
                ),
              _PageKind.playlists => _buildPlaylistIndex(),
              _PageKind.albums => _buildAlbumIndex(),
              _PageKind.playlist => _buildTrackCollection(
                  '${_selectedPlaylist?['title'] ?? context.l10n.yandexUnknownPlaylist}',
                  _detailTracks,
                  _detailSource,
                  _detailLastUpdated,
                  _refreshDetail,
                  back: _showPlaylists,
                ),
              _PageKind.album => _buildTrackCollection(
                  '${_selectedAlbum?['title'] ?? context.l10n.yandexUnknownAlbum}',
                  _detailTracks,
                  _detailSource,
                  _detailLastUpdated,
                  _refreshDetail,
                  back: _showAlbums,
                ),
            },
          ),
        ],
      );

  Widget _tabs() {
    final selected = _page == _PageKind.liked
        ? _PageKind.liked
        : (_page == _PageKind.albums || _page == _PageKind.album
            ? _PageKind.albums
            : _PageKind.playlists);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SegmentedButton<_PageKind>(
        key: const Key('yandex-primary-tabs'),
        showSelectedIcon: false,
        segments: [
          ButtonSegment(
            value: _PageKind.liked,
            icon: const Icon(Icons.favorite_outline),
            label: Text(
              context.l10n.yandexLikedTab,
              key: const Key('nav-liked'),
            ),
          ),
          ButtonSegment(
            value: _PageKind.playlists,
            icon: const Icon(Icons.queue_music),
            label: Text(
              context.l10n.yandexPlaylistsTab,
              key: const Key('nav-playlists'),
            ),
          ),
          ButtonSegment(
            value: _PageKind.albums,
            icon: const Icon(Icons.album_outlined),
            label: Text(
              context.l10n.yandexAlbumsTab,
              key: const Key('nav-albums'),
            ),
          ),
        ],
        selected: {selected},
        onSelectionChanged: (values) {
          if (values.contains(_PageKind.liked)) {
            _showLiked();
          } else if (values.contains(_PageKind.albums)) {
            _showAlbums();
          } else {
            _showPlaylists();
          }
        },
      ),
    );
  }

  Widget _header(
    String title,
    int count,
    String unit,
    String source,
    String? updated,
    Future<void> Function() refresh, {
    VoidCallback? back,
  }) =>
      Padding(
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              context.l10n.yandexLibraryTitle,
              style: Theme.of(context).textTheme.labelLarge,
            ),
            if (back != null)
              TextButton.icon(
                key: Key(
                  _page == _PageKind.album
                      ? 'yandex-back-to-albums'
                      : 'yandex-back-to-playlists',
                ),
                onPressed: back,
                icon: const Icon(Icons.arrow_back),
                label: Text(
                  _page == _PageKind.album
                      ? context.l10n.yandexBackToAlbums
                      : context.l10n.yandexBackToPlaylists,
                ),
              ),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context)
                            .textTheme
                            .headlineMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '$count $unit • ${_relativeTime(updated)} • ${_sourceLabel(source)}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                IconButton.filledTonal(
                  key: const Key('refresh-library'),
                  onPressed: _busy
                      ? null
                      : () {
                          refresh();
                        },
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _tabs(),
          ],
        ),
      );

  String _sourceLabel(String source) => switch (source) {
        'network' => context.l10n.yandexSourceNetwork,
        'cache' => context.l10n.yandexSourceCache,
        _ => context.l10n.yandexSourceNone,
      };

  String _relativeTime(String? raw) {
    final parsed = raw == null ? null : DateTime.tryParse(raw)?.toLocal();
    if (parsed == null) return context.l10n.yandexNeverUpdated;
    var diff = DateTime.now().difference(parsed);
    if (diff.isNegative) diff = Duration.zero;
    if (diff.inMinutes < 1) return context.l10n.yandexUpdatedJustNow;
    if (diff.inMinutes < 60) {
      return '${diff.inMinutes} ${context.l10n.yandexMinutesAgoSuffix}';
    }
    return '${diff.inHours} ${context.l10n.yandexHoursAgoSuffix}';
  }

  Widget _buildTrackCollection(
    String title,
    List<Map<String, dynamic>> tracks,
    String source,
    String? updated,
    Future<void> Function() refresh, {
    VoidCallback? back,
  }) {
    final visible = _visibleTracks;
    return Column(
      children: [
        _header(
          title,
          tracks.length,
          context.l10n.yandexTracksLabel,
          source,
          updated,
          refresh,
          back: back,
        ),
        _trackToolbar(),
        Expanded(
          child: visible.isEmpty
              ? Center(child: Text(context.l10n.yandexNoSearchTitle))
              : LayoutBuilder(
                  builder: (context, constraints) {
                    final wide =
                        constraints.maxWidth >= AppUiTokens.yandexTableWide;
                    return Column(
                      children: [
                        if (wide) const _TrackHeader(),
                        Expanded(
                          child: ListView.builder(
                            key: const Key('track-list'),
                            itemExtent: 72,
                            itemCount: visible.length,
                            itemBuilder: (context, index) {
                              final track = visible[index];
                              final externalId = _id(track);
                              return _TrackRow(
                                track: track,
                                label: _contentLabels[externalId],
                                wide: wide,
                                busy: _playingTrackId == externalId,
                                labelEnabled:
                                    widget.contentLabelBridge != null,
                                onPlay:
                                    '${track['availability'] ?? ''}' ==
                                            'unavailable'
                                        ? null
                                        : () => _play(track),
                                onLabel: widget.contentLabelBridge == null
                                    ? null
                                    : (value) => _setLabel(track, value),
                              );
                            },
                          ),
                        ),
                      ],
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _trackToolbar() => Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final search = TextField(
              key: const Key('track-search'),
              controller: _searchController,
              onChanged: _scheduleTrackSearch,
              onSubmitted: _submitTrackSearch,
              decoration: InputDecoration(
                hintText: context.l10n.yandexSearchTracks,
                prefixIcon: const Icon(Icons.search),
              ),
            );
            final sort = DropdownButtonFormField<LibrarySort>(
              key: Key('track-sort-${_trackSort.name}'),
              initialValue: _trackSort,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: context.l10n.yandexSortLabel,
              ),
              items: [
                DropdownMenuItem(
                  value: LibrarySort.original,
                  child: Text(context.l10n.yandexSortOriginal),
                ),
                DropdownMenuItem(
                  value: LibrarySort.title,
                  child: Text(context.l10n.yandexSortTitle),
                ),
                DropdownMenuItem(
                  value: LibrarySort.artist,
                  child: Text(context.l10n.yandexSortArtist),
                ),
                DropdownMenuItem(
                  value: LibrarySort.unavailable,
                  child: Text(context.l10n.yandexSortUnavailable),
                ),
              ],
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value != null) {
                        setState(() {
                          _trackSort = value;
                          _invalidateVisibleTracks();
                        });
                      }
                    },
            );
            final labels = widget.contentLabelBridge == null
                ? null
                : YandexContentLabelsButton(
                    bridge: widget.bridge,
                    labelBridge: widget.contentLabelBridge,
                  );
            if (constraints.maxWidth >= AppUiTokens.yandexToolbarWide) {
              return Row(
                children: [
                  Expanded(child: search),
                  const SizedBox(width: 12),
                  SizedBox(width: 230, child: sort),
                  if (labels != null) ...[
                    const SizedBox(width: 8),
                    labels,
                  ],
                ],
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                search,
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    SizedBox(width: 230, child: sort),
                    if (labels != null) labels,
                  ],
                ),
              ],
            );
          },
        ),
      );

  Widget _buildPlaylistIndex() {
    final visible = _visiblePlaylists;
    return Column(
      children: [
        _header(
          context.l10n.yandexPlaylistsTab,
          _playlists.length,
          context.l10n.yandexPlaylistsLabel,
          _playlistsSource,
          _playlistsLastUpdated,
          _refreshLibrary,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final search = TextField(
                key: const Key('playlist-search'),
                controller: _searchController,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: context.l10n.yandexSearchPlaylists,
                  prefixIcon: const Icon(Icons.search),
                ),
              );
              final sort = DropdownButtonFormField<PlaylistSort>(
                key: Key('playlist-sort-${_playlistSort.name}'),
                initialValue: _playlistSort,
                isExpanded: true,
                items: [
                  DropdownMenuItem(
                    value: PlaylistSort.original,
                    child: Text(context.l10n.yandexSortOriginal),
                  ),
                  DropdownMenuItem(
                    value: PlaylistSort.title,
                    child: Text(context.l10n.yandexSortTitle),
                  ),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => _playlistSort = value);
                },
              );
              if (constraints.maxWidth >= 700) {
                return Row(
                  children: [
                    Expanded(child: search),
                    const SizedBox(width: 12),
                    SizedBox(width: 230, child: sort),
                  ],
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  search,
                  const SizedBox(height: 8),
                  SizedBox(width: 230, child: sort),
                ],
              );
            },
          ),
        ),
        Expanded(
          child: ListView.separated(
            key: const Key('playlist-list'),
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
            itemCount: visible.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final item = visible[index];
              final externalId = _id(item);
              final count = int.tryParse('${item['trackCount'] ?? 0}') ?? 0;
              final owner = '${item['ownerName'] ?? ''}'.trim();
              return Card(
                key: Key('playlist-row-$externalId'),
                child: ListTile(
                  title: Text(
                    '${item['title'] ?? context.l10n.yandexUnknownPlaylist}',
                  ),
                  subtitle: owner.isEmpty ? null : Text(owner),
                  trailing: Text('$count ${context.l10n.yandexTracksLabel}'),
                  onTap: () => _openPlaylist(item),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildAlbumIndex() {
    final visible = _visibleAlbums;
    return Column(
      children: [
        _header(
          context.l10n.yandexFavoriteAlbumsTitle,
          _likedAlbums.length,
          context.l10n.yandexAlbumsLabel,
          _albumsSource,
          _albumsLastUpdated,
          _refreshLibrary,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
          child: TextField(
            key: const Key('album-search'),
            controller: _searchController,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              hintText: context.l10n.yandexSearchAlbums,
              prefixIcon: const Icon(Icons.search),
            ),
          ),
        ),
        Expanded(
          child: visible.isEmpty
              ? Center(child: Text(context.l10n.yandexEmptyAlbumsTitle))
              : LayoutBuilder(
                  builder: (context, constraints) {
                    final proposed = (constraints.maxWidth / 220).floor();
                    final columns = proposed.clamp(1, 6).toInt();
                    return GridView.builder(
                      key: const Key('album-list'),
                      padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
                      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: columns,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                        childAspectRatio: .86,
                      ),
                      itemCount: visible.length,
                      itemBuilder: (context, index) => _AlbumCard(
                        album: visible[index],
                        onTap: () => _openAlbum(visible[index]),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, this.details});

  final String message;
  final String? details;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('error-panel'),
        color: Theme.of(context).colorScheme.errorContainer,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(message),
              if (details?.isNotEmpty == true)
                Text(details!, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      );
}

class _AlbumCard extends StatelessWidget {
  const _AlbumCard({required this.album, required this.onTap});

  final Map<String, dynamic> album;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final id = '${album['externalId'] ?? ''}';
    final artists = album['artists'] is List
        ? (album['artists'] as List).join(', ')
        : '${album['artists'] ?? ''}';
    final artwork = '${album['artworkUrl'] ?? ''}'.trim();
    final count = int.tryParse('${album['trackCount'] ?? 0}') ?? 0;
    return Card(
      key: Key('album-card-$id'),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: AppUiTokens.mediumRadius,
                  child: SizedBox.expand(
                    child: artwork.isEmpty
                        ? ColoredBox(
                            color: Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                            child: const Icon(Icons.album_outlined, size: 54),
                          )
                        : Image.network(
                            artwork,
                            fit: BoxFit.cover,
                            cacheWidth: 512,
                            cacheHeight: 512,
                            errorBuilder: (_, _, _) => ColoredBox(
                              color: Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHighest,
                              child: const Icon(Icons.album_outlined, size: 54),
                            ),
                          ),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                '${album['title'] ?? context.l10n.yandexUnknownAlbum}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              Text(
                artists.isEmpty ? context.l10n.yandexUnknownArtist : artists,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              Text(
                '$count ${context.l10n.yandexTracksLabel}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TrackHeader extends StatelessWidget {
  const _TrackHeader();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(32, 0, 32, 4),
        child: Row(
          children: [
            const SizedBox(width: 60),
            Expanded(child: Text(context.l10n.yandexTrackColumn)),
            SizedBox(
              width: 220,
              child: Text(context.l10n.yandexAlbumColumn),
            ),
            SizedBox(
              width: 112,
              child: Text(context.l10n.yandexLabelColumn),
            ),
            SizedBox(
              width: 58,
              child: Text(context.l10n.yandexTimeColumn),
            ),
            const SizedBox(width: 96),
          ],
        ),
      );
}

class _TrackRow extends StatelessWidget {
  const _TrackRow({
    required this.track,
    required this.label,
    required this.wide,
    required this.busy,
    required this.labelEnabled,
    required this.onPlay,
    required this.onLabel,
  });

  final Map<String, dynamic> track;
  final String? label;
  final bool wide;
  final bool busy;
  final bool labelEnabled;
  final VoidCallback? onPlay;
  final ValueChanged<String>? onLabel;

  String _duration(dynamic raw) {
    final seconds = raw is int ? raw : int.tryParse('${raw ?? ''}');
    if (seconds == null) return '—';
    return '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final id = '${track['external_id'] ?? track['externalId'] ?? ''}';
    final title = '${track['title'] ?? context.l10n.yandexUnknownTitle}';
    final artists = track['artists'] is List
        ? (track['artists'] as List).join(', ')
        : '${track['artists'] ?? context.l10n.yandexUnknownArtist}';
    final album = '${track['album_title'] ?? ''}';
    final unavailable = '${track['availability'] ?? ''}' == 'unavailable';
    final duration = _duration(track['duration_seconds']);
    final artwork =
        '${track['artwork_url'] ?? track['artworkUrl'] ?? ''}'.trim();
    final hasLabel = label?.isNotEmpty == true;

    Widget chip() => !hasLabel
        ? const SizedBox.shrink()
        : Chip(
            key: Key('yandex-inline-content-label-$id'),
            visualDensity: VisualDensity.compact,
            label: Text(
              label == 'censored'
                  ? context.l10n.censored
                  : context.l10n.original,
            ),
          );

    Widget actions() => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (labelEnabled && onLabel != null)
              PopupMenuButton<String>(
                key: Key('yandex-inline-content-label-menu-$id'),
                initialValue: hasLabel ? label : null,
                onSelected: onLabel!,
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'original',
                    child: Text(context.l10n.original),
                  ),
                  PopupMenuItem(
                    value: 'censored',
                    child: Text(context.l10n.censored),
                  ),
                  const PopupMenuDivider(),
                  PopupMenuItem(
                    value: '',
                    child: Text(context.l10n.yandexClearLabel),
                  ),
                ],
                icon: const Icon(Icons.sell_outlined),
              ),
            Tooltip(
              message: unavailable
                  ? context.l10n.yandexTrackUnavailable
                  : context.l10n.play,
              child: IconButton(
                key: Key('yandex-play-$id'),
                onPressed: busy || unavailable ? null : onPlay,
                icon: busy
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow),
              ),
            ),
          ],
        );

    return Opacity(
      opacity: unavailable ? .58 : 1,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 2),
        child: Container(
          key: Key('yandex-track-$id'),
          constraints: const BoxConstraints(minHeight: 68),
          child: Row(
            children: [
              ClipRRect(
                key: Key('yandex-artwork-$id'),
                borderRadius: AppUiTokens.smallRadius,
                child: SizedBox(
                  width: 48,
                  height: 48,
                  child: artwork.isEmpty
                      ? ColoredBox(
                          color: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
                          child: const Icon(Icons.music_note),
                        )
                      : Image.network(
                          artwork,
                          fit: BoxFit.cover,
                          cacheWidth: 96,
                          cacheHeight: 96,
                          errorBuilder: (_, _, _) => ColoredBox(
                            color: Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                            child: const Icon(Icons.music_note),
                          ),
                        ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      wide
                          ? artists
                          : [
                              artists,
                              if (album.isNotEmpty) album,
                              duration,
                            ].join(' • '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              if (wide) ...[
                SizedBox(
                  width: 220,
                  child: Text(
                    album.isEmpty ? '—' : album,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                SizedBox(width: 112, child: chip()),
                SizedBox(width: 58, child: Text(duration)),
              ] else if (hasLabel) ...[
                const SizedBox(width: 8),
                chip(),
              ],
              SizedBox(
                width: 96,
                child: Align(
                  alignment: Alignment.centerRight,
                  child: actions(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
