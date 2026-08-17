import 'package:flutter/foundation.dart';

import 'musicark_bridge.dart';

class AccountSessionController extends ChangeNotifier {
  bool _initializing = true;
  bool _hasStoredToken = false;
  Map<String, dynamic> _account = const {};
  int _logoutRevision = 0;

  bool get initializing => _initializing;
  bool get isSignedIn => _hasStoredToken;
  Map<String, dynamic> get account => Map.unmodifiable(_account);
  int get logoutRevision => _logoutRevision;

  String get displayName => '${_account['displayName'] ?? ''}'.trim();
  String get providerUserId => '${_account['providerUserId'] ?? ''}'.trim();

  static String _firstRune(String value) =>
      value.isEmpty ? '' : String.fromCharCode(value.runes.first);

  String get initials {
    final clean = displayName.trim();
    if (clean.isEmpty) return '';
    final parts = clean
        .split(RegExp(r'\s+'))
        .where((item) => item.isNotEmpty)
        .toList();
    if (parts.length == 1) return _firstRune(parts.first).toUpperCase();
    return '${_firstRune(parts.first)}${_firstRune(parts[1])}'.toUpperCase();
  }

  void applyPayload(Map<String, dynamic> payload) {
    final rawSession = payload['session'];
    if (rawSession is! Map) return;
    final session = Map<String, dynamic>.from(rawSession);
    final signedIn = session['hasStoredToken'] == true;
    final rawAccount = session['account'];
    final incomingAccount = rawAccount is Map
        ? Map<String, dynamic>.from(rawAccount)
        : <String, dynamic>{};

    final signedOutNow = _hasStoredToken && !signedIn;
    _hasStoredToken = signedIn;
    if (!signedIn) {
      _account = const {};
    } else if (incomingAccount.isNotEmpty) {
      _account = incomingAccount;
    }
    _initializing = false;
    if (signedOutNow) _logoutRevision++;
    notifyListeners();
  }

  void finishInitialization() {
    if (!_initializing) return;
    _initializing = false;
    notifyListeners();
  }
}

class SessionAwareMusicArkBridge implements MusicArkBridgeClient {
  SessionAwareMusicArkBridge(this._delegate, this._session);

  final MusicArkBridgeClient _delegate;
  final AccountSessionController _session;

  Future<Map<String, dynamic>> _accountResult(
    Future<Map<String, dynamic>> Function() operation,
  ) async {
    final payload = await operation();
    _session.applyPayload(payload);
    return payload;
  }

  @override
  Future<Map<String, dynamic>> bootstrap() => _accountResult(_delegate.bootstrap);
  @override
  Future<Map<String, dynamic>> login(String token) =>
      _accountResult(() => _delegate.login(token));
  @override
  Future<Map<String, dynamic>> likedRefresh() =>
      _accountResult(_delegate.likedRefresh);
  @override
  Future<Map<String, dynamic>> playlists() => _accountResult(_delegate.playlists);
  @override
  Future<Map<String, dynamic>> playlist(String externalId) =>
      _accountResult(() => _delegate.playlist(externalId));
  @override
  Future<Map<String, dynamic>> playlistRefresh(String externalId) =>
      _accountResult(() => _delegate.playlistRefresh(externalId));
  @override
  Future<Map<String, dynamic>> albums() => _accountResult(_delegate.albums);
  @override
  Future<Map<String, dynamic>> album(String externalId) =>
      _accountResult(() => _delegate.album(externalId));
  @override
  Future<Map<String, dynamic>> albumRefresh(String externalId) =>
      _accountResult(() => _delegate.albumRefresh(externalId));
  @override
  Future<Map<String, dynamic>> libraryRefresh() =>
      _accountResult(_delegate.libraryRefresh);
  @override
  Future<Map<String, dynamic>> logout() => _accountResult(_delegate.logout);
  @override
  Future<Map<String, dynamic>> yandexPlaybackPrepare(String externalId) =>
      _delegate.yandexPlaybackPrepare(externalId);
  @override
  Future<Map<String, dynamic>> localRoots() => _delegate.localRoots();
  @override
  Future<Map<String, dynamic>> localRootAdd(String path) =>
      _delegate.localRootAdd(path);
  @override
  Future<Map<String, dynamic>> localRootRemove(int rootId) =>
      _delegate.localRootRemove(rootId);
  @override
  Future<Map<String, dynamic>> localScan({int? rootId}) =>
      _delegate.localScan(rootId: rootId);
  @override
  Future<Map<String, dynamic>> localTracks({
    int limit = 1000,
    int offset = 0,
    String search = '',
    String sort = 'artist',
    int? rootId,
    List<int>? rootIds,
  }) =>
      _delegate.localTracks(
        limit: limit,
        offset: offset,
        search: search,
        sort: sort,
        rootId: rootId,
        rootIds: rootIds,
      );
  @override
  Future<Map<String, dynamic>> localTrack(int trackId) =>
      _delegate.localTrack(trackId);
  @override
  Future<Map<String, dynamic>> localStats() => _delegate.localStats();
}
