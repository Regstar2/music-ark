import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/account_session.dart';
import 'package:musicark_ui/musicark_bridge.dart';

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

  test('session bridge reuses prepared Yandex playback without a second bridge call', () async {
    final session = AccountSessionController();
    final delegate = FakeMusicArkBridge(startSignedIn: true);
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
