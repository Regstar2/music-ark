import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:musicark_ui/main.dart';
import 'package:musicark_ui/musicark_bridge.dart';

void main() {
  Future<void> desktop(WidgetTester tester, MusicArkBridgeClient bridge) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    await tester.pumpWidget(MusicArkDesktopApp(bridge: bridge));
    await tester.pumpAndSettle();
  }

  testWidgets('cached session shows sidebar and Liked without entering a token', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await desktop(tester, bridge);
    expect(find.byKey(const Key('library-sidebar')), findsOneWidget);
    expect(find.byKey(const Key('nav-liked')), findsOneWidget);
    expect(find.byKey(const Key('nav-playlists')), findsOneWidget);
    expect(find.byKey(const Key('logout-button')), findsNothing);
    expect(find.byKey(const Key('global-account-menu')), findsOneWidget);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.text('Animal I Have Become'), findsOneWidget);
    expect(find.text('Вход в Яндекс Музыку'), findsNothing);
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('playlist list opens cached playlist and track search works', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await desktop(tester, bridge);
    await tester.tap(find.byKey(const Key('nav-playlists')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('playlist-list')), findsOneWidget);
    expect(find.byKey(const Key('playlist-row-501')), findsOneWidget);
    expect(find.byKey(const Key('playlist-row-502')), findsOneWidget);
    await tester.tap(find.byKey(const Key('playlist-row-501')));
    await tester.pumpAndSettle();
    expect(find.text('Numb'), findsOneWidget);
    expect(find.text('Bring Me to Life'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('track-search')), 'Evanescence');
    await tester.pump();
    expect(find.text('Bring Me to Life'), findsOneWidget);
    expect(find.text('Numb'), findsNothing);
    expect(bridge.playlistRefreshCalls, 1);
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('track sorting, full refresh, and global logout remain available', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true);
    await desktop(tester, bridge);
    expect(
      tester.getTopLeft(find.text('Courtesy Call')).dy,
      lessThan(tester.getTopLeft(find.text('Animal I Have Become')).dy),
    );
    await tester.tap(find.byKey(const Key('track-sort-original')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('По названию').last);
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text('Animal I Have Become')).dy,
      lessThan(tester.getTopLeft(find.text('Courtesy Call')).dy),
    );
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
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('network refresh error keeps cached library visible', (tester) async {
    final bridge = FakeMusicArkBridge(startSignedIn: true, failLibraryRefresh: true);
    await desktop(tester, bridge);
    expect(find.text('Courtesy Call'), findsOneWidget);
    expect(find.byKey(const Key('error-panel')), findsOneWidget);
    expect(
      find.text(
        'Не удалось обновить данные из Яндекс Музыки. Показана сохранённая версия.',
      ),
      findsOneWidget,
    );
    await tester.binding.setSurfaceSize(null);
  });
}
