import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/musicark_bridge.dart';

class _PlaybackPathBridge extends FakeMusicArkBridge {
  _PlaybackPathBridge(this.path) : super(startSignedIn: true);

  final String path;

  @override
  Future<Map<String, dynamic>> yandexPlaybackPrepare(String externalId) async {
    yandexPlaybackPrepareCalls++;
    return {
      'providerId': 'yandex_music',
      'externalId': externalId,
      'path': path,
      'cached': false,
      'preparationState': 'downloaded',
      'timingsMs': {'total': 1.0},
    };
  }
}

void main() {
  test('account mapping exposes initials without credentials', () {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {
          'provider': 'yandex_music',
          'providerUserId': '42',
          'displayName': 'Иван Петров',
        },
      },
    });

    expect(session.isSignedIn, isTrue);
    expect(session.displayName, 'Иван Петров');
    expect(session.providerUserId, '42');
    expect(session.initials, 'ИП');
    expect(session.account.containsKey('token'), isFalse);
  });

  test('single word account name uses one initial', () {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {'displayName': 'Regstar2'},
      },
    });

    expect(session.initials, 'R');
  });

  test('signed-in payload without account does not erase cached profile', () {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {'displayName': 'Cached User'},
      },
    });
    session.applyPayload({
      'session': {'hasStoredToken': true, 'account': <String, dynamic>{}},
    });

    expect(session.isSignedIn, isTrue);
    expect(session.displayName, 'Cached User');
  });

  test('logout clears account and advances logout revision', () {
    final session = AccountSessionController();
    session.applyPayload({
      'session': {
        'hasStoredToken': true,
        'account': {'displayName': 'User'},
      },
    });
    expect(session.logoutRevision, 0);

    session.applyPayload({
      'session': {'hasStoredToken': false, 'account': <String, dynamic>{}},
    });

    expect(session.isSignedIn, isFalse);
    expect(session.displayName, isEmpty);
    expect(session.logoutRevision, 1);
  });

  test('session bridge reuses an existing prepared Yandex playback path', () async {
    final temp = await Directory.systemTemp.createTemp('musicark-playback-');
    addTearDown(() => temp.delete(recursive: true));
    final audio = File('${temp.path}${Platform.pathSeparator}track.mp3');
    await audio.writeAsBytes([1, 2, 3]);

    final session = AccountSessionController();
    final delegate = _PlaybackPathBridge(audio.path);
    final bridge = SessionAwareMusicArkBridge(delegate, session);

    final first = await bridge.yandexPlaybackPrepare('101');
    final second = await bridge.yandexPlaybackPrepare('101');

    expect(delegate.yandexPlaybackPrepareCalls, 1);
    expect(first['timingsMs'], isA<Map>());
    expect((first['timingsMs'] as Map)['bridgeRoundTrip'], isA<num>());
    expect(second['cached'], isTrue);
    expect(second['preparationState'], 'memory_cache_hit');
    expect((second['timingsMs'] as Map)['bridgeRoundTrip'], 0.0);

    await bridge.logout();
    await bridge.yandexPlaybackPrepare('101');
    expect(delegate.yandexPlaybackPrepareCalls, 2);
  });
}
