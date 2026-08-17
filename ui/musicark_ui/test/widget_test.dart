import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/content_label_bridge.dart';
import 'package:musicark_ui/main.dart';

class _FakeContentLabelBridge implements ContentLabelBridgeClient {
  final Map<String, String> provider = {'101': 'original', '102': 'censored'};

  @override
  Future<Map<String, dynamic>> batch({
    List<int> localFileIds = const [],
    List<String> externalIds = const [],
    String providerId = 'yandex_music',
  }) async => {
        'local': <String, String>{},
        'provider': {
          for (final id in externalIds)
            if (provider[id] != null) id: provider[id],
        },
      };

  @override
  Future<Map<String, dynamic>> setLocal(int localFileId, String label) async => {};

  @override
  Future<Map<String, dynamic>> setProvider(
    String externalId,
    String label, {
    String providerId = 'yandex_music',
  }) async {
    label.isEmpty ? provider.remove(externalId) : provider[externalId] = label;
    return {'externalId': externalId, 'label': label};
  }
}

class _StatefulSessionFake extends FakeMusicArkBridge {
  _StatefulSessionFake() : super(startSignedIn: true);
  bool _loggedOut = false;
  @override
  Future<Map<String, dynamic>> bootstrap() => _loggedOut ? super.logout() : super.bootstrap();
  @override
  Future<Map<String, dynamic>> logout() async {
    _loggedOut = true;
    return super.logout();
  }
}

class _UnavailableSecondBridge extends FakeMusicArkBridge {
  _UnavailableSecondBridge() : super(startSignedIn: true);

  Map<String, dynamic> _patch(Map<String, dynamic> input) {
    final payload = Map<String, dynamic>.from(input);
    final liked = Map<String, dynamic>.from(payload['liked'] as Map);
    final tracks = (liked['tracks'] as List)
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
    if (tracks.length > 1) tracks[1]['availability'] = 'unavailable';
    liked['tracks'] = tracks;
    payload['liked'] = liked;
    payload['library'] = liked;
    return payload;
  }

  @override
  Future<Map<String, dynamic>> bootstrap() async => _patch(await super.bootstrap());
  @override
  Future<Map<String, dynamic>> likedRefresh() async => _patch(await super.likedRefresh());
  @override
  Future<Map<String, dynamic>> libraryRefresh() async => _patch(await super.libraryRefresh());
}

void main() {
  Future<void> desktop(WidgetTester tester, MusicArkBridgeClient bridge) async {
    tester.platformDispatcher.localeTestValue = const Locale('ru');
    addTearDown(tester.platformDispatcher.clearLocaleTestValue);
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MusicArkDesktopApp(
        bridge: bridge,
        contentLabelBridge: _FakeContentLabelBridge(),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('cached session uses one primary sidebar and Yandex tabs', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await desktop(tester, bridge);
    expect(find.byKey(const Key('musicark-primary-sidebar')), findsOneWidget);
    expect(find.byKey(const Key('library-sidebar')), findsNothing);
    expect(find.byKey(const Key('yandex-primary-tabs')), findsOneWidget);
    expect(find.byKey(const Key('nav-liked')), findsOneWidget);
    expect(find.byKey(const Key('nav-playlists')), findsOneWidget);
    expect(find.byKey(const Key('nav-albums')), findsOneWidget);
    expect(find.byKey(const Key('global-account-menu')), findsOneWidget);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.text('Animal I Have Become'), findsOneWidget);
    expect(find.text('available'), findsNothing);
    expect(find.text('Вход в Яндекс Музыку'), findsNothing);
  });

  testWidgets('playlist index opens detail, search works and back returns to index', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await desktop(tester, bridge);
    await tester.tap(find.byKey(const Key('nav-playlists')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('playlist-list')), findsOneWidget);
    expect(find.byKey(const Key('playlist-row-501')), findsOneWidget);
    expect(find.byKey(const Key('playlist-row-502')), findsOneWidget);
    await tester.tap(find.byKey(const Key('playlist-row-501')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('yandex-back-to-playlists')), findsOneWidget);
    expect(find.text('Numb'), findsOneWidget);
    expect(find.text('Bring Me to Life'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('track-search')), 'Evanescence');
    await tester.pump();
    expect(find.text('Bring Me to Life'), findsOneWidget);
    expect(find.text('Numb'), findsNothing);
    expect(bridge.playlistRefreshCalls, 1);
    await tester.tap(find.byKey(const Key('yandex-back-to-playlists')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('playlist-list')), findsOneWidget);
  });

  testWidgets('liked albums come from the provider collection and open full album detail', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await desktop(tester, bridge);
    await tester.tap(find.byKey(const Key('nav-albums')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('album-list')), findsOneWidget);
    expect(find.text('Hybrid Theory'), findsOneWidget);
    expect(find.text('The Open Door'), findsOneWidget);
    expect(find.text('The End Is Where We Begin'), findsNothing);
    expect(find.text('One-X'), findsNothing);

    await tester.tap(find.byKey(const Key('album-card-701')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('yandex-back-to-albums')), findsOneWidget);
    expect(find.text('Papercut'), findsOneWidget);
    expect(find.text('In the End'), findsOneWidget);
    expect(find.text('Courtesy Call'), findsNothing);
    expect(bridge.albumRefreshCalls, 1);

    await tester.tap(find.byKey(const Key('yandex-back-to-albums')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('album-list')), findsOneWidget);
  });

  testWidgets('track sorting, refresh and global logout remain available', (tester) async {
    final bridge = _StatefulSessionFake();
    await desktop(tester, bridge);
    expect(tester.getTopLeft(find.text('Courtesy Call')).dy, lessThan(tester.getTopLeft(find.text('Animal I Have Become')).dy));
    await tester.tap(find.byKey(const Key('track-sort-original')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('По названию').last);
    await tester.pumpAndSettle();
    expect(tester.getTopLeft(find.text('Animal I Have Become')).dy, lessThan(tester.getTopLeft(find.text('Courtesy Call')).dy));
    final automaticRefreshes = bridge.libraryRefreshCalls;
    await tester.tap(find.byKey(const Key('refresh-library')));
    await tester.pumpAndSettle();
    expect(bridge.libraryRefreshCalls, automaticRefreshes + 1);
    await tester.tap(find.byKey(const Key('global-account-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Выйти'));
    await tester.pumpAndSettle();
    expect(find.text('Вход в Яндекс Музыку'), findsOneWidget);
    expect(find.byKey(const Key('global-account-sign-in')), findsOneWidget);
  });

  testWidgets('unavailable sort moves unavailable tracks to the top', (tester) async {
    final bridge = _UnavailableSecondBridge();
    await desktop(tester, bridge);
    expect(tester.getTopLeft(find.text('Courtesy Call')).dy, lessThan(tester.getTopLeft(find.text('Animal I Have Become')).dy));
    await tester.tap(find.byKey(const Key('track-sort-original')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Недоступные сначала').last);
    await tester.pumpAndSettle();
    expect(tester.getTopLeft(find.text('Animal I Have Become')).dy, lessThan(tester.getTopLeft(find.text('Courtesy Call')).dy));
    final unavailablePlay = tester.widget<IconButton>(find.byKey(const Key('yandex-play-102')));
    expect(unavailablePlay.onPressed, isNull);
  });

  testWidgets('network refresh error keeps cached library visible', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true, failLibraryRefresh: true);
    await desktop(tester, bridge);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.byKey(const Key('error-panel')), findsOneWidget);
    expect(find.text('Не удалось обновить данные из Яндекс Музыки. Показана сохранённая версия.'), findsOneWidget);
  });
}
